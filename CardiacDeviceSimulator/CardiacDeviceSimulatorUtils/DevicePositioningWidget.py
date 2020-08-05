import ctk, qt, vtk
import slicer
import logging
from CardiacDeviceSimulatorUtils.widgethelper import UIHelper
from CardiacDeviceSimulatorUtils.widgethelper import DeviceWidget


class DevicePositioningWidget(DeviceWidget):
  """
  """

  @staticmethod
  def createHLayout(elements):
    widget = qt.QWidget()
    rowLayout = qt.QHBoxLayout()
    widget.setLayout(rowLayout)
    for element in elements:
      rowLayout.addWidget(element)
    return widget

  def __init__(self, parent=None):
    DeviceWidget.__init__(self, parent)
    self.observedParameterNodeEvents = [vtk.vtkCommand.ModifiedEvent]
    self.setup()

  def setup(self):
    self.setLayout(qt.QFormLayout())

    lay = self.layout()

    self.vesselGroupBox = qt.QGroupBox("Vessel lumen")
    self.vesselGroupBox.setLayout(qt.QFormLayout())

    # vessel lumen
    self.vesselSegmentSelector = slicer.qMRMLSegmentSelectorWidget()
    self.vesselSegmentSelector.setMRMLScene(slicer.mrmlScene)
    self.vesselSegmentSelector.setToolTip("Select vessel lumen (blood) segment. The segment must be a solid, filled "
                                          "model of the blood (not a shell).")
    self.vesselGroupBox.layout().addRow("Segmentation Node: ", self.vesselSegmentSelector)
    self.vesselSegmentSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onVesselLumenSegmentSelectionChanged)
    self.vesselSegmentSelector.connect("currentSegmentChanged(QString)", self.onVesselLumenSegmentSelectionChanged)

    # Button to position device at closest centerline point
    self.processVesselSegmentButton = qt.QPushButton("Detect vessel centerline")
    self.processVesselSegmentButton.setToolTip("Extract centerline and lumen surface from vessel segment")
    self.vesselGroupBox.layout().addRow(self.processVesselSegmentButton)
    self.processVesselSegmentButton.connect('clicked(bool)', self.onProcessVesselSegmentClicked)
    self.processVesselSegmentButton.enabled = bool(self.vesselSegmentSelector.currentSegmentID())

    lay.addRow(self.vesselGroupBox)

    # Centerline curve node selector

    self.centerlineGroupBox = qt.QGroupBox("Centerline")
    self.centerlineGroupBox.setLayout(qt.QFormLayout())

    self.centerLineObservers = list()
    self.centerlineNodeSelector = slicer.qMRMLNodeComboBox()
    self.centerlineNodeSelector.nodeTypes = ["vtkMRMLMarkupsCurveNode"]
    self.centerlineNodeSelector.setNodeTypeLabel("Centerline", "vtkMRMLMarkupsCurveNode")
    self.centerlineNodeSelector.baseName = "Centerline"
    self.centerlineNodeSelector.selectNodeUponCreation = True
    self.centerlineNodeSelector.addEnabled = True
    self.centerlineNodeSelector.removeEnabled = True
    self.centerlineNodeSelector.noneEnabled = True
    self.centerlineNodeSelector.showHidden = True
    self.centerlineNodeSelector.renameEnabled = True
    self.centerlineNodeSelector.setMRMLScene(slicer.mrmlScene)
    self.centerlineNodeSelector.setToolTip("Select a curve to be used for positioning the device")
    self.centerlineNodeSelector.connect("currentNodeChanged(vtkMRMLNode*)",
                                        self.onCenterlineNodeSelectionChanged)

    self.centerlinePlaceWidget = slicer.qSlicerMarkupsPlaceWidget()
    self.centerlinePlaceWidget.setMRMLScene(slicer.mrmlScene)

    self.centerLineHBox = self.createHLayout([qt.QLabel("Centerline curve: "), self.centerlineNodeSelector,
                                              self.centerlinePlaceWidget])

    self.centerlineGroupBox.layout().addRow(self.centerLineHBox)

    # Button to position device at closest centerline point
    self.positionDeviceAtCenterlineButton = qt.QPushButton("Position device at centerline")
    self.centerlineGroupBox.layout().addRow(self.positionDeviceAtCenterlineButton)
    self.positionDeviceAtCenterlineButton.connect('clicked(bool)', self.onPositionDeviceAtCenterlineClicked)
    self.positionDeviceAtCenterlineButton.enabled = (self.centerlineNodeSelector.currentNode() is not None)

    # Button to flip device orientation
    self.flipDeviceOrientationButton = qt.QPushButton("Flip device orientation")
    self.centerlineGroupBox.layout().addRow(self.flipDeviceOrientationButton)
    self.flipDeviceOrientationButton.connect('clicked(bool)', self.onFlipDeviceOrientationClicked)
    self.flipDeviceOrientationButton.enabled = (self.centerlineNodeSelector.currentNode() is not None)

    # Pick centerline model
    self.deviceCenterLineSliderBox = qt.QHBoxLayout()
    self.deviceCenterLineSliderBox.addWidget(qt.QLabel("Slide along centerline:"))
    self.moveDeviceAlongCenterlineSliderWidget = UIHelper.createSliderWidget({
      "info": "Moves the device along extracted centerline", "value": 0,
      "unit": "", "minimum": 0, "maximum": 100, "singleStep": 0.1, "pageStep": 1, "decimals": 1},
      self.onMoveDeviceAlongCenterlineSliderChanged)
    self.deviceCenterLineSliderBox.addWidget(self.moveDeviceAlongCenterlineSliderWidget)
    self.moveDeviceAlongCenterlineSliderWidget.enabled = (self.centerlineNodeSelector.currentNode() is not None)

    self.adjustOrientationCheckbox = qt.QCheckBox("align orientation")
    self.adjustOrientationCheckbox.checked = True
    self.deviceCenterLineSliderBox.addWidget(self.adjustOrientationCheckbox)
    self.centerlineGroupBox.layout().addRow(self.deviceCenterLineSliderBox)

    lay.addRow(self.centerlineGroupBox)

    # Position
    self.devicePositioningPositionSliderWidget = slicer.qMRMLTransformSliders()
    self.devicePositioningPositionSliderWidget.Title = 'Device position'
    self.devicePositioningPositionSliderWidget.TypeOfTransform = slicer.qMRMLTransformSliders.TRANSLATION
    self.devicePositioningPositionSliderWidget.CoordinateReference = slicer.qMRMLTransformSliders.LOCAL
    self.devicePositioningPositionSliderWidget.setMRMLScene(slicer.mrmlScene)
    self.devicePositioningPositionSliderWidget.setMRMLTransformNode(None)
    self.devicePositioningPositionSliderWidget.findChildren(ctk.ctkCollapsibleGroupBox)[0].setChecked(False)
    lay.addRow(self.devicePositioningPositionSliderWidget)

    # Orientation
    self.devicePositioningOrientationSliderWidget = slicer.qMRMLTransformSliders()
    self.devicePositioningOrientationSliderWidget.Title = 'Device orientation'
    self.devicePositioningOrientationSliderWidget.setMRMLScene(slicer.mrmlScene)
    # Setting of qMRMLTransformSliders.TypeOfTransform is not robust: it has to be set after setMRMLScene and
    # has to be set twice (with setting the type to something else in between).
    # Therefore the following 3 lines are needed, and needed here:
    self.devicePositioningOrientationSliderWidget.TypeOfTransform = slicer.qMRMLTransformSliders.ROTATION
    self.devicePositioningOrientationSliderWidget.TypeOfTransform = slicer.qMRMLTransformSliders.TRANSLATION
    self.devicePositioningOrientationSliderWidget.TypeOfTransform = slicer.qMRMLTransformSliders.ROTATION
    self.devicePositioningOrientationSliderWidget.CoordinateReference = slicer.qMRMLTransformSliders.LOCAL
    self.devicePositioningOrientationSliderWidget.minMaxVisible = False
    self.devicePositioningOrientationSliderWidget.setMRMLTransformNode(None)
    self.devicePositioningOrientationSliderWidget.findChildren(ctk.ctkCollapsibleGroupBox)[0].setChecked(False)
    lay.addRow(self.devicePositioningOrientationSliderWidget)

    # TODO: once orientation changed, checkbox for orientation should be disabled when placing along the center line

    self.vesselSegmentSelector.connect('currentNodeChanged(bool)', self.processVesselSegmentButton, 'setEnabled(bool)')

  def setParameterNode(self, parameterNode):
    DeviceWidget.setParameterNode(self, parameterNode)

  def updateGUIFromMRML(self, caller=None, event=None):
    positioningTransform = self.parameterNode.GetNodeReference('PositioningTransform') if self.parameterNode else None
    self.devicePositioningPositionSliderWidget.setMRMLTransformNode(positioningTransform)
    self.devicePositioningOrientationSliderWidget.setMRMLTransformNode(positioningTransform)
    self.centerlineNodeSelector.setCurrentNode(self.logic.getCenterlineNode())
    segment = self.logic.getVesselLumenSegment()
    [vesselLumenSegmentationNode, vesselLumenSegmentId] = segment if segment else [None, ""]
    self.vesselSegmentSelector.setCurrentNode(vesselLumenSegmentationNode)
    self.vesselSegmentSelector.setCurrentSegmentID(vesselLumenSegmentId)
    self.onCenterlineNodeSelectionChanged()

  def onCenterlineNodeSelectionChanged(self):
    self._removeCenterlineNodeObservers(self.logic.getCenterlineNode())
    currentNode = self.centerlineNodeSelector.currentNode()
    self.centerlinePlaceWidget.setCurrentNode(currentNode)
    self.logic.setCenterlineNode(currentNode)
    self._addCenterlineNodeObservers(currentNode)
    self._onCenterlineNodeModified(currentNode)
    self._updatedCenterlineSlider(currentNode)

  def _removeCenterlineNodeObservers(self, previousNode):
    if self.centerLineObservers and previousNode is not None:
      for observer in self.centerLineObservers:
        previousNode.RemoveObserver(observer)
      self.centerLineObservers = list()

  def _addCenterlineNodeObservers(self, currentNode):
    try:
      for evt in [slicer.vtkMRMLMarkupsNode.PointAddedEvent, slicer.vtkMRMLMarkupsNode.PointRemovedEvent]:
        self.centerLineObservers.append(currentNode.AddObserver(evt, self._onCenterlineNodeModified))
    except AttributeError:
      pass

  def _onCenterlineNodeModified(self, centerLineNode, caller=None):
    enabled = centerLineNode is not None and centerLineNode.GetNumberOfControlPoints() > 1
    self.positionDeviceAtCenterlineButton.setEnabled(enabled)
    self.flipDeviceOrientationButton.setEnabled(enabled)
    self.moveDeviceAlongCenterlineSliderWidget.setEnabled(enabled)

  def _updatedCenterlineSlider(self, currentNode):
    if not currentNode:
      return
    storedSliderPosition = self.logic.getDeviceCenterlinePosition()
    if storedSliderPosition:
      oldBlockSignalsState = self.moveDeviceAlongCenterlineSliderWidget.blockSignals(True)
      self.moveDeviceAlongCenterlineSliderWidget.value = storedSliderPosition
      self.moveDeviceAlongCenterlineSliderWidget.blockSignals(oldBlockSignalsState)

  def onProcessVesselSegmentClicked(self):
    self.logic.processVesselSegment()
    self.centerlineNodeSelector.setCurrentNode(self.logic.getCenterlineNode())
    [vesselLumenSegmentationNode, vesselLumenSegmentId] = self.logic.getVesselLumenSegment()

    # Optimize visibility
    vesselLumenModelNode = self.logic.getVesselModelNode()
    if vesselLumenModelNode:
      # hide segment to make the semi-transparent vessel surface visible instead
      vesselLumenSegmentationNode.GetDisplayNode().SetVisibility(False)

  def onPositionDeviceAtCenterlineClicked(self):
    logging.debug("positioning device at centerline endpoint")
    deviceCenter = self.logic.getDeviceCenter()
    normalizedPosition = self.logic.getNormalizedPositionAlongCenterline(deviceCenter)
    sliderValue = int(round(normalizedPosition*100.0))
    self.moveDeviceAlongCenterlineSliderWidget.setValue(sliderValue)
    # Force snapping, even if the slider value did not change
    self.onMoveDeviceAlongCenterlineSliderChanged()

  def onFlipDeviceOrientationClicked(self):
    logging.debug("flipped device orientation")
    self.logic.setDeviceOrientationFlippedOnCenterline(not self.logic.getDeviceOrientationFlippedOnCenterline())
    self.onMoveDeviceAlongCenterlineSliderChanged()  # force refresh

  def onMoveDeviceAlongCenterlineSliderChanged(self):
    sliderValue = self.moveDeviceAlongCenterlineSliderWidget.value
    self.logic.setDeviceCenterlinePosition(sliderValue)
    self.logic.setDeviceNormalizedPositionAlongCenterline(sliderValue * 0.01, self.adjustOrientationCheckbox.checked)

  def onVesselLumenSegmentSelectionChanged(self):
    self.logic.setVesselLumenSegment(self.vesselSegmentSelector.currentNode(), self.vesselSegmentSelector.currentSegmentID())

import QtQuick
import QtQml.Models
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import qs.Ui
import qs.Commons
import "GapModel.js" as GapModel

BarWidget {
  id: root
  moduleName: "tommy.show-desktop"
  activeFocusOnTab: true
  Accessible.role: Accessible.Button
  Accessible.name: "Show desktop"
  Accessible.onPressAction: root.toggleDesktop()
  Keys.onPressed: function(event) {
    if (event.key === Qt.Key_Space || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
      event.accepted = true
      if (!event.isAutoRepeat) root.toggleDesktop()
    }
  }

  // Use the same public per-surface monitor lookup as Omarchy's Workspaces.
  // Do not fall back to another monitor when this surface has no monitor yet.
  readonly property var targetMonitor: {
    const window = root.QsWindow.window
    return window && window.screen ? Hyprland.monitorFor(window.screen) : null
  }
  function toggleDesktop() {
    const workspace = targetMonitor ? targetMonitor.activeWorkspace : null
    const id = workspace ? workspace.id : -1
    if (toggleProcess.running || !Number.isInteger(id) || id < 1) return
    toggleProcess.command = ["hyprctl", "eval", "o.show_desktop.toggle(" + id + ")"]
    toggleProcess.running = true
  }
  property var observedNeighbors: []
  property real gapWidth: Style.space(36)
  implicitWidth: gapWidth

  // Codex review: private ancestor/pool API; upstream layout integration is required.
  // The current Omarchy bar gives each surface a widget pool. Read its live
  // geometry so the red region stops at the desktop numbers and the clock.
  function neighbors() {
    let item = root.parent
    while (item && !item.pool) item = item.parent
    const hosts = item && item.pool ? item.pool.hosts : null
    let workspaces = null, clock = null
    let ownRegion = "", workspaceRegion = "", clockRegion = ""
    const ownStart = root.mapToItem(null, 0, 0).x
    let independentStart = Infinity, leftFollower = false
    let observed = []
    if (hosts) for (const key in hosts) {
      const host = hosts[key]
      const region = host.owner ? String(host.owner.region || "") : ""
      if (host.activeItem === root) ownRegion = region
      const active = host.activeItem
      if (active && active !== root) {
        let ancestor = active
        while (ancestor) {
          if (ancestor !== root && observed.indexOf(ancestor) === -1) observed.push(ancestor)
          ancestor = ancestor.parent
        }
      }
      if (active && active !== root && active.visible) {
        const start = active.mapToItem(null, 0, 0).x
        if (region === "left" && start >= ownStart) leftFollower = true
        if (["center", "centerBegin", "centerEnd", "right"].indexOf(region) !== -1)
          independentStart = Math.min(independentStart, start)
      }
      if (host.moduleName === "omarchy.workspaces") {
        workspaces = host.activeItem
        workspaceRegion = region
      }
      if (host.moduleName === "omarchy.clock") {
        clock = host.activeItem
        clockRegion = region
      }
    }
    return {workspaces:workspaces, clock:clock,
      ownRegion:ownRegion, workspaceRegion:workspaceRegion, clockRegion:clockRegion,
      independentStart:independentStart, leftFollower:leftFollower, observed:observed}
  }
  function resizeGap() {
    const n = neighbors()
    if (n.observed.length !== observedNeighbors.length ||
        n.observed.some((item, index) => item !== observedNeighbors[index]))
      observedNeighbors = n.observed
    const surface = root.QsWindow.window
    const next = GapModel.widthFor({
      vertical: vertical, barSize: barSize, compact: Style.space(36), margin: Style.space(4),
      ownRegion: n.ownRegion, workspaceRegion: n.workspaceRegion, clockRegion: n.clockRegion,
      independentStart: n.independentStart, leftFollower: n.leftFollower,
      ownStart: root.mapToItem(null, 0, 0).x,
      workspaceEnd: n.workspaces ? n.workspaces.mapToItem(null, n.workspaces.width, 0).x : NaN,
      clockStart: n.clock ? n.clock.mapToItem(null, 0, 0).x : NaN,
      surfaceWidth: surface ? surface.width : NaN
    })
    if (Math.abs(next-gapWidth) >= 1) gapWidth = next
  }
  onVerticalChanged: resizeGap()
  onBarSizeChanged: resizeGap()
  onXChanged: resizeGap()
  onWidthChanged: resizeGap()
  Component.onCompleted: resizeGap()
  Connections {
    target: root.QsWindow.window
    ignoreUnknownSignals: true
    function onWidthChanged() { root.resizeGap() }
  }
  Instantiator {
    model: root.observedNeighbors
    delegate: Connections {
      required property var modelData
      target: modelData
      ignoreUnknownSignals: true
      function onXChanged() { root.resizeGap() }
      function onYChanged() { root.resizeGap() }
      function onWidthChanged() { root.resizeGap() }
      function onVisibleChanged() { root.resizeGap() }
      function onParentChanged() { root.resizeGap() }
    }
  }
  // Membership in the private host pool has no public change signal.
  Timer { interval: 2000; running: root.visible; repeat: true; onTriggered: root.resizeGap() }
  implicitHeight: barSize

  Rectangle {
    anchors.fill: parent
    anchors.topMargin: Style.space(3)
    anchors.bottomMargin: Style.space(3)
    radius: Style.space(4)
    color: mouse.pressed ? "#590b13" : mouse.containsMouse ? "#941f2b" : "#780d1a"
    border.width: 1
    border.color: root.activeFocus ? "#df8b96" : "#a33b47"
  }
  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    acceptedButtons: Qt.LeftButton
    onClicked: root.toggleDesktop()
  }
  Process {
    id: toggleProcess
    // Command is assigned only after a positive integer workspace is captured.
    onExited: function(exitCode, exitStatus) {
      if (exitCode !== 0) console.warn("Show desktop request failed")
    }
  }
}

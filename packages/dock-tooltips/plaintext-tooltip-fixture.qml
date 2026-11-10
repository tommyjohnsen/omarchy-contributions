import QtQuick
import Quickshell
import qs.Ui as Ui
ShellRoot {
  property string unusualName: "<b>Test app</b> & <img src='not-a-resource'>"
  Ui.PanelToolTip { id: tip; text: unusualName; visible: false }
  Timer {
    interval: 300
    running: true
    onTriggered: {
      function fail(message) { console.error("FAIL: " + message); Qt.exit(1); }
      if (Quickshell.env("FIXTURE_FORCE_FAILURE") === "1") return fail("intentional negative fixture");
      if (tip.contentItem.textFormat !== Text.PlainText) return fail("Tooltip permits markup");
      if (tip.contentItem.text !== unusualName) return fail("App name changed");
      if (tip.delay !== 400) return fail("Hover delay changed");
      console.log("PASS: markup-shaped app names remain plain text; hover delay 400ms.");
      Qt.exit(0);
    }
  }
}

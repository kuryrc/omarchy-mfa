import QtQuick
import Quickshell

ShellRoot {
    property int phase: 0
    property string mode: Quickshell.env("MFA_TEST_MODE")
    Window {
        visible: true
        width: 1000
        height: 800
        Mfa {
            id: mfa
            anchors.fill: parent
        }
    }
    Timer {
        interval: 50
        running: true
        repeat: true
        onTriggered: {
            if (phase === 0) {
                mfa.open("{}");
                phase++;
                return;
            }
            if (phase === 1) {
                if (mfa.busy || !mfa.accounts.length)
                    return;
                mfa.activate(mode !== "copy_only");
                phase++;
                return;
            }
            if (mfa.busy)
                return;
            var error = mode === "copy_failed" ? "keyring_write_failed" : mode.indexOf("malformed") === 0 ? "backend_failed" : "paste_failed";
            var success = mode === "success" || mode === "copy_only";
            var okay = success ? !mfa.opened && !mfa.testPanel.visible : mfa.opened && mfa.testPanel.visible && mfa.errorCode === error && !mfa.pasteToken;
            console.log("MFA_PASTE_CHECK " + (okay ? "PASS " : "FAIL ") + mode + " completed with correct visibility and error");
            console.log("MFA_PASTE_DONE");
            Qt.quit();
        }
    }
    Timer {
        interval: 5000
        running: true
        onTriggered: {
            console.log("MFA_PASTE_CHECK FAIL timed out");
            Qt.quit();
        }
    }
}

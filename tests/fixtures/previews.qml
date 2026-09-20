import QtQuick
import Quickshell
import qs.Commons

ShellRoot {
    id: capture
    property int step: 0
    property bool capturing: false
    property string filename: ""

    function take(name) {
        filename = name;
        capturing = true;
        settle.restart();
    }

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
        id: settle
        interval: 150
        onTriggered: {
            mfa.captureCard.forceActiveFocus();
            if (!mfa.captureCard.grabToImage(function (result) {
                if (!result.saveToFile(Quickshell.env("MFA_PREVIEW_OUTPUT") + "/" + capture.filename)) {
                    console.log("MFA_PREVIEW_FAILED save");
                    Qt.quit();
                    return;
                }
                console.log("MFA_PREVIEW_SAVED " + capture.filename);
                capture.step++;
                capture.capturing = false;
            }, Qt.size(1520, 1180))) {
                console.log("MFA_PREVIEW_FAILED grab");
                Qt.quit();
            }
        }
    }

    Timer {
        interval: 50
        repeat: true
        running: !capture.capturing
        onTriggered: {
            if (capture.step === 0) {
                mfa.open("{}");
                capture.step++;
                return;
            }
            if (mfa.busy || mfa.accounts.length !== 5)
                return;
            mfa.captureClock.running = false;
            mfa.now = 1700000000;
            if (capture.step === 1) {
                capture.take("accounts.png");
            } else if (capture.step === 2) {
                mfa.go("actions");
                mfa.captureActions.currentIndex = 4;
                capture.take("actions.png");
            } else if (capture.step === 3) {
                mfa.runAction("add");
                mfa.captureName.text = "Example Cloud · demo@example.com";
                // Public RFC 6238 test secret; never saved or sent to a real backend.
                mfa.captureSecret.text = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ";
                capture.take("add-account.png");
            } else if (capture.step === 4) {
                if (mfa.page !== "preview") {
                    mfa.previewImport();
                    return;
                }
                capture.take("restore-preview.png");
            } else if (capture.step === 5) {
                mfa.settings = ({
                        language: "zh",
                        defaultAction: "copy"
                    });
                mfa.runAction("settings");
                capture.take("settings-zh.png");
            } else {
                console.log("MFA_PREVIEW_DONE");
                Qt.quit();
            }
        }
    }
}

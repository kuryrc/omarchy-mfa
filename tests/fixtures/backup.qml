import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import QtTest

ShellRoot {
    id: h
    property int phase: 0
    property int cycles: 0
    property var mfa: testMfa
    function check(ok, detail) {
        console.log("MFA_BACKUP_CHECK " + (ok ? "PASS " : "FAIL ") + detail);
        if (!ok)
            Qt.quit();
        return ok;
    }
    function find(item, predicate) {
        if (predicate(item))
            return item;
        var children = item.children || [];
        for (var i = 0; i < children.length; i++) {
            var result = find(children[i], predicate);
            if (result)
                return result;
        }
        return null;
    }
    function visibleItem(predicate) {
        return find(mfa.testWindow.contentItem, function (i) {
            return i.visible && predicate(i);
        });
    }
    function dialogList() {
        return visibleItem(function (i) {
            return /DialogListView/.test(i.objectName);
        });
    }
    function click(item) {
        return item && keys.mouseClick(item, item.width / 2, item.height / 2, Qt.LeftButton, Qt.NoModifier, 0);
    }
    function button(text) {
        return visibleItem(function (i) {
            return i.text !== undefined && i.text.replace(/&/g, "") === text && i.clicked !== undefined && i.enabled;
        });
    }
    function action(name) {
        mfa.testActions.currentIndex = mfa.testActions.model.indexOf(name);
        mfa.testActions.forceActiveFocus();
        keys.keyClick(Qt.Key_Return, Qt.NoModifier, 0);
    }
    TestEvent {
        id: keys
    }
    Window {
        visible: true
        width: 1000
        height: 800
        Mfa {
            id: testMfa
            anchors.fill: parent
        }
    }
    Timer {
        interval: 100
        repeat: true
        running: true
        onTriggered: {
            if (h.phase === 0) {
                mfa.open("{}");
                h.phase++;
                return;
            }
            if (!mfa.opened) {
                h.check(false, "test overlay was closed before completion");
                return;
            }
            if (!mfa.testWindow || mfa.busy)
                return;
            if (h.phase === 1) {
                if (mfa.accounts.length !== 2 || !mfa.testWindow.active)
                    return;
                mfa.go("actions");
                h.phase++;
                return;
            }
            if (h.phase === 2) {
                h.action("backup");
                h.phase++;
                return;
            }
            if (h.phase === 3) {
                if (!h.check(mfa.testConfirmation.opened && !mfa.testFile.visible && !h.dialogList(), "backup asks for confirmation without a file or folder chooser (page=" + mfa.page + ", selection=" + mfa.testActions.currentIndex + ")"))
                    return;
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                h.phase++;
                return;
            }
            if (h.phase === 4) {
                if (!h.check(!mfa.testConfirmation.opened && mfa.page === "actions", "cancel backup confirmation preserves navigation"))
                    return;
                h.action("backup");
                h.phase++;
                return;
            }
            if (h.phase === 5) {
                if (!h.check(mfa.testConfirmation.opened, "automatic backup still requires plaintext confirmation"))
                    return;
                keys.keyClick(Qt.Key_Right, Qt.NoModifier, 0);
                keys.keyClick(Qt.Key_Return, Qt.NoModifier, 0);
                h.phase++;
                return;
            }
            if (h.phase === 6) {
                if (!h.check(mfa.page === "list" && mfa.message.indexOf(mfa.tr("exported") + Quickshell.env("MFA_TEST_DESTINATION_PATH") + "/") === 0, "backup creates a file automatically and displays its full path"))
                    return;
                mfa.go("actions");
                h.phase = 13;
                return;
            }
            if (h.phase === 13) {
                h.action("restore");
                h.phase++;
                return;
            }
            if (h.phase === 14) {
                if (!h.check(mfa.page === "import", "Restore opens the source page"))
                    return;
                mfa.testFile.currentFolder = Quickshell.env("MFA_TEST_DESTINATION");
                h.click(h.button(mfa.tr("browse")));
                h.phase++;
                return;
            }
            if (h.phase === 15) {
                if (!h.check(mfa.testFile.visible && h.dialogList(), "restore chooser opens inside the MFA window"))
                    return;
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                h.phase++;
                return;
            }
            if (h.phase === 16) {
                if (!h.check(!mfa.testFile.visible && mfa.page === "import" && mfa.testSource.text === "", "cancel restore chooser leaves source unchanged"))
                    return;
                h.click(h.button(mfa.tr("browse")));
                h.phase++;
                return;
            }
            if (h.phase === 17) {
                var view = h.dialogList();
                if (!view || view.count !== 1 || !view.itemAtIndex(0))
                    return;
                h.click(view.itemAtIndex(0));
                h.phase++;
                return;
            }
            if (h.phase === 18) {
                h.click(h.button("Open"));
                h.phase++;
                return;
            }
            if (h.phase === 19) {
                if (!h.check(!mfa.testFile.visible && mfa.testSource.text.indexOf(Quickshell.env("MFA_TEST_DESTINATION_PATH") + "/") === 0, "file selection handles Chinese and spaces"))
                    return;
                h.click(h.button(mfa.tr("preview")));
                h.phase++;
                return;
            }
            if (h.phase === 20) {
                if (!h.check(mfa.page === "preview" && mfa.testRows.count === 2 && mfa.testRows.get(0).conflict && !mfa.testRows.get(0).checked, "exported backup previews with existing entries skipped"))
                    return;
                mfa.testPreview.currentIndex = 0;
                mfa.testPreview.forceActiveFocus();
                keys.keyClick(Qt.Key_Space, Qt.NoModifier, 0);
                keys.keyClick(Qt.Key_Down, Qt.NoModifier, 0);
                keys.keyClick(Qt.Key_Space, Qt.NoModifier, 0);
                h.click(h.button(mfa.tr("importSelected")));
                h.phase++;
                return;
            }
            if (h.phase === 21) {
                if (!h.check(mfa.testConfirmation.opened, "overwrite requires explicit confirmation"))
                    return;
                keys.keyClick(Qt.Key_Right, Qt.NoModifier, 0);
                keys.keyClick(Qt.Key_Return, Qt.NoModifier, 0);
                h.phase++;
                return;
            }
            if (h.phase === 22) {
                if (!h.check(mfa.page === "list" && mfa.message.indexOf(mfa.tr("overwrittenCount") + " 2") >= 0, "restore completes with two reported overwrites"))
                    return;
                mfa.go("actions");
                h.phase++;
                return;
            }
            if (h.phase === 23) {
                h.action("backup");
                h.phase++;
                return;
            }
            if (h.phase === 24) {
                if (!h.check(mfa.testConfirmation.opened && !mfa.testFile.visible, "reopen backup confirmation without a chooser, cycle " + h.cycles))
                    return;
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                h.phase++;
                return;
            }
            if (h.phase === 25) {
                h.action("restore");
                h.phase++;
                return;
            }
            if (h.phase === 26) {
                h.click(h.button(mfa.tr("browse")));
                h.phase++;
                return;
            }
            if (h.phase === 27) {
                if (!h.check(mfa.testFile.visible, "reopen restore chooser, cycle " + h.cycles))
                    return;
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                h.phase++;
                return;
            }
            if (h.phase === 28) {
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!h.check(mfa.page === "actions", "Esc returns from source to Actions"))
                    return;
                h.cycles++;
                h.phase = h.cycles < 5 ? 23 : 29;
                return;
            }
            if (h.phase === 29) {
                console.log("MFA_BACKUP_DONE");
                mfa.close();
                Qt.quit();
            }
        }
    }
    Timer {
        interval: 15000
        running: true
        onTriggered: {
            console.log("MFA_BACKUP_CHECK FAIL timeout phase " + h.phase + " busy=" + mfa.busy + " error=" + mfa.errorCode + " window=" + Boolean(mfa.testWindow));
            Qt.quit();
        }
    }
}

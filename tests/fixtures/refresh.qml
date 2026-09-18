import QtQuick
import Quickshell
import QtTest

ShellRoot {
    id: harness
    property int phase: 0
    property real oldY: 0
    property real oldHeight: 0
    property int oldIndex: 0
    property double highlightReadyAt: 0
    function check(ok, detail) {
        console.log("MFA_UI_CHECK " + (ok ? "PASS" : "FAIL") + " " + detail);
        if (!ok)
            Qt.quit();
        return ok;
    }
    function checkMovement(view, context) {
        var page = mfa.page, text = mfa.testSearch.text;
        view.currentIndex = 0;
        keys.keyClick(Qt.Key_N, Qt.ControlModifier, 0);
        if (!check(mfa.page === page && view.currentIndex === 1 && mfa.testSearch.text === text, context + ": Ctrl+n selects next without changing page or search"))
            return false;
        keys.keyClick(Qt.Key_P, Qt.ControlModifier, 0);
        if (!check(view.currentIndex === 0, context + ": Ctrl+p selects previous"))
            return false;
        keys.keyClick(Qt.Key_P, Qt.ControlModifier, 0);
        if (!check(view.currentIndex === (page === "list" ? view.count - 1 : 0), context + ": upper boundary matches arrow keys"))
            return false;
        view.currentIndex = view.count - 1;
        keys.keyClick(Qt.Key_N, Qt.ControlModifier, 0);
        if (!check(view.currentIndex === (page === "list" ? 0 : view.count - 1), context + ": lower boundary matches arrow keys"))
            return false;
        view.currentIndex = 0;
        return true;
    }
    function paintedHighlights(view) {
        var count = view.highlightItem && view.highlightItem.visible && view.highlightItem.color !== undefined && view.highlightItem.color.a > 0 ? 1 : 0;
        for (var i = 0; i < view.count; i++) {
            var item = view.itemAtIndex(i);
            if (item && (item.color.a > 0 || item.borderLeft > 0 || item.borderRight > 0 || item.borderTop > 0 || item.borderBottom > 0))
                count++;
        }
        return count;
    }
    Window {
        id: testWindow
        visible: true
        width: 1000
        height: 800
        Mfa {
            id: mfa
        }
        TestEvent {
            id: keys
        }
    }
    Timer {
        interval: 50
        running: true
        repeat: true
        onTriggered: {
            var view = mfa.testView;
            if (harness.phase === 0)
                mfa.open("{}");
            if (harness.phase === 6) {
                view.currentIndex = 20;
                view.positionViewAtIndex(20, ListView.Center);
            }
            if (harness.phase === 8) {
                if (mfa.busy)
                    return;
                harness.oldY = view.contentY;
                harness.oldHeight = view.height;
                harness.oldIndex = view.currentIndex;
                mfa.refresh();
            }
            if (harness.phase === 9 || harness.phase === 13) {
                var ok = harness.oldHeight > 0 && harness.oldHeight === view.height && harness.oldY === view.contentY && harness.oldIndex === view.currentIndex;
                if (!harness.check(ok, "refresh phase=" + harness.phase + " height=" + harness.oldHeight + "->" + view.height + " offset=" + harness.oldY + "->" + view.contentY + " selection=" + harness.oldIndex + "->" + view.currentIndex))
                    return;
            }
            if (harness.phase === 14) {
                if (mfa.busy)
                    return;
                testWindow.requestActivate();
                mfa.testSearch.forceActiveFocus();
                mfa.testSearch.text = "Fixture";
                mfa.testSearch.cursorPosition = 0;
                if (!harness.checkMovement(view, "account list"))
                    return;
                var focused = mfa.testSearch.activeFocus;
                var sent = keys.keyClick(Qt.Key_K, Qt.ControlModifier, 0);
                if (!harness.check(focused && sent && mfa.page === "actions" && mfa.testSearch.text === "Fixture", "Ctrl+k opens actions from search without deleting text"))
                    return;
            }
            if (harness.phase === 15) {
                keys.keyClick(Qt.Key_K, Qt.ControlModifier, 0);
                if (!harness.check(mfa.page === "list", "Ctrl+k returns from actions"))
                    return;
            }
            if (harness.phase === 16) {
                if (mfa.busy)
                    return;
                mfa.testSearch.cursorPosition = 0;
                keys.keyClick(Qt.Key_K, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "list" && mfa.testSearch.text === "kFixture", "plain k remains search input"))
                    return;
                mfa.testSearch.text = "Fixture";
                mfa.testSearch.cursorPosition = 0;
                keys.keyClick(Qt.Key_P, Qt.NoModifier, 0);
                keys.keyClick(Qt.Key_N, Qt.NoModifier, 0);
                if (!harness.check(mfa.testSearch.text === "pnFixture", "plain p and n remain search input"))
                    return;
                mfa.testSearch.text = "Fixture";
                mfa.testSearch.cursorPosition = 0;
                mfa.refresh();
                var refreshing = mfa.busy && mfa.backgroundRefresh;
                if (!harness.checkMovement(view, "background refresh"))
                    return;
                keys.keyClick(Qt.Key_K, Qt.ControlModifier, 0);
                if (!harness.check(refreshing && mfa.page === "actions" && mfa.testSearch.text === "Fixture", "Ctrl+k works during background refresh"))
                    return;
            }
            if (harness.phase === 17) {
                keys.keyClick(Qt.Key_K, Qt.ControlModifier, 0);
                if (!harness.check(mfa.page === "list", "Ctrl+k returns during background refresh"))
                    return;
            }
            if (harness.phase === 18) {
                if (mfa.busy)
                    return;
                keys.keyClick(Qt.Key_K, Qt.ControlModifier, 0);
            }
            if (harness.phase === 19) {
                var hovered = mfa.testActions.itemAtIndex(mfa.testActions.count - 1);
                keys.mouseMove(hovered, 10, hovered.height / 2, 0, Qt.NoButton, Qt.NoModifier);
                keys.keyClick(Qt.Key_P, Qt.ControlModifier, 0);
                keys.keyClick(Qt.Key_P, Qt.ControlModifier, 0);
                harness.highlightReadyAt = Date.now() + 160;
            }
            if (harness.phase === 20) {
                if (Date.now() < harness.highlightReadyAt)
                    return;
                var count = harness.paintedHighlights(mfa.testActions);
                if (!harness.check(mfa.testActions.currentIndex === mfa.testActions.count - 3 && count === 1, "keyboard selection with stationary mouse has one highlight; painted=" + count))
                    return;
                var highlight = mfa.testActions.highlightItem, current = mfa.testActions.currentItem;
                if (!harness.check(highlight && highlight.width === current.width && highlight.height === current.height && highlight.y === current.y, "single highlight covers the current row"))
                    return;
                keys.keyClick(Qt.Key_N, Qt.ControlModifier, 0);
                keys.keyClick(Qt.Key_P, Qt.ControlModifier, 0);
                if (!harness.check(harness.paintedHighlights(mfa.testActions) === 1, "rapid movement leaves no fading duplicate highlight"))
                    return;
                keys.keyClick(Qt.Key_Tab, Qt.NoModifier, 0);
                if (!harness.check(mfa.testActions.currentItem.activeFocus && harness.paintedHighlights(mfa.testActions) === 1, "Tab focus agrees with the single selection"))
                    return;
                keys.keyClick(Qt.Key_K, Qt.ControlModifier, 0);
            }
            if (harness.phase === 21) {
                if (mfa.busy)
                    return;
                keys.keyClick(Qt.Key_K, Qt.ControlModifier, 0);
                mfa.testActions.currentIndex = 0;
            }
            if (harness.phase === 22) {
                if (!harness.checkMovement(mfa.testActions, "Actions"))
                    return;
                for (var i = 0; i < 2; i++)
                    keys.keyClick(Qt.Key_Down, Qt.NoModifier, 0);
                for (var i = 0; i < 3; i++)
                    keys.keyClick(Qt.Key_N, Qt.ControlModifier, 0);
                if (!harness.check(mfa.testActions.model[mfa.testActions.currentIndex] === "addUrl", "arrow keys and Ctrl+n select Add by otpauth URL"))
                    return;
                keys.keyClick(Qt.Key_Return, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "url", "Return activates highlighted action"))
                    return;
            }
            if (harness.phase === 23) {
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "actions", "Esc from URL form returns to Actions"))
                    return;
            }
            if (harness.phase === 24) {
                keys.keyClick(Qt.Key_Enter, Qt.KeypadModifier, 0);
                if (!harness.check(mfa.page === "url", "keypad Enter activates highlighted action"))
                    return;
            }
            if (harness.phase === 25) {
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
            }
            if (harness.phase === 26) {
                var item = mfa.testActions.itemAtIndex(4);
                keys.mouseMove(item, 10, item.height / 2, 0, Qt.NoButton, Qt.NoModifier);
                if (!harness.check(mfa.testActions.model[mfa.testActions.currentIndex] === "add", "mouse hover selects Add account"))
                    return;
                keys.keyClick(Qt.Key_Return, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "add", "Return activates mouse-highlighted action"))
                    return;
            }
            if (harness.phase === 27) {
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "actions" && mfa.testActions.model[mfa.testActions.currentIndex] === "add", "Esc from Add account returns to Actions with selection preserved"))
                    return;
            }
            if (harness.phase === 28) {
                keys.keyClick(Qt.Key_Down, Qt.NoModifier, 0);
                keys.keyClick(Qt.Key_Space, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "url", "Space activates highlighted action"))
                    return;
            }
            if (harness.phase === 29) {
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "actions", "Esc returns one level after reopening a form"))
                    return;
            }
            if (harness.phase === 30) {
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "list" && mfa.opened, "second Esc returns from Actions to main list"))
                    return;
            }
            if (harness.phase === 31) {
                if (mfa.busy)
                    return;
                keys.keyClick(Qt.Key_N, Qt.ControlModifier | Qt.ShiftModifier, 0);
                if (!harness.check(mfa.page === "add", "Ctrl+Shift+n opens Add account directly from main list"))
                    return;
            }
            if (harness.phase === 32) {
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "list" && mfa.opened, "Esc from directly opened form returns to main list"))
                    return;
            }
            if (harness.phase === 33) {
                if (mfa.busy)
                    return;
                keys.keyClick(Qt.Key_K, Qt.ControlModifier, 0);
            }
            if (harness.phase === 34) {
                var item = mfa.testActions.itemAtIndex(mfa.testActions.model.indexOf("settings"));
                keys.mouseClick(item, 10, item.height / 2, Qt.LeftButton, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "settings", "mouse click still opens Settings from Actions"))
                    return;
            }
            if (harness.phase === 35) {
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "actions" && mfa.testActions.model[mfa.testActions.currentIndex] === "settings", "Esc from Settings restores menu selection"))
                    return;
            }
            if (harness.phase === 36) {
                mfa.testActions.currentIndex = mfa.testActions.model.indexOf("rename");
                keys.keyClick(Qt.Key_Return, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "rename", "Rename opens from Actions"))
                    return;
            }
            if (harness.phase === 37) {
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "actions", "Esc from Rename returns to Actions"))
                    return;
            }
            if (harness.phase === 38) {
                mfa.testActions.currentIndex = mfa.testActions.model.indexOf("restore");
                keys.keyClick(Qt.Key_Return, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "import", "Restore opens from Actions"))
                    return;
            }
            if (harness.phase === 39)
                mfa.previewImport();
            if (harness.phase === 40) {
                if (mfa.busy)
                    return;
                if (!harness.check(mfa.page === "preview" && mfa.previewToken !== "", "restore preview opens"))
                    return;
                if (!harness.checkMovement(mfa.testPreview, "import preview"))
                    return;
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "import" && mfa.previewToken === "", "Esc cancels preview and returns to backup path"))
                    return;
            }
            if (harness.phase === 41) {
                if (mfa.busy)
                    return;
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!harness.check(mfa.page === "actions", "next Esc returns from backup path to Actions"))
                    return;
            }
            if (harness.phase === 42) {
                mfa.testActions.currentIndex = mfa.testActions.model.indexOf("rename");
                keys.keyClick(Qt.Key_Return, Qt.NoModifier, 0);
            }
            if (harness.phase === 43)
                mfa.saveAccount(false);
            if (harness.phase === 44) {
                if (mfa.busy)
                    return;
                if (!harness.check(mfa.page === "list", "successful save returns to main list"))
                    return;
                keys.keyClick(Qt.Key_Escape, Qt.NoModifier, 0);
                if (!harness.check(!mfa.opened, "Esc after save closes popup without reopening old pages"))
                    return;
                console.log("MFA_UI_DONE");
                Qt.quit();
            }
            harness.phase++;
        }
    }
}

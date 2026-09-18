import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import QtQuick.Controls as Controls
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui as Ui
import "I18n.js" as I18n

Item {
    id: root
    property var shell: null
    property var manifest: null
    property bool opened: false
    property bool busy: false
    property bool backgroundRefresh: false
    property string page: "list"
    property var pageHistory: []
    property var accounts: []
    property var settings: ({
            language: "auto",
            defaultAction: "copy"
        })
    property string vaultRevision: ""
    property string message: ""
    property string errorCode: ""
    property string previewToken: ""
    property string pasteToken: ""
    property string selectedAccountId: ""
    property int serial: 0
    property var pending: ({})
    property var confirmCallback: null
    property real now: Date.now() / 1000
    readonly property string localeName: Quickshell.env("LC_ALL") || Quickshell.env("LC_MESSAGES") || Quickshell.env("LANG") || "en"
    readonly property string language: I18n.language(settings.language, localeName)
    readonly property string backendPath: decodeURIComponent(Qt.resolvedUrl("backend/backend.py").toString().replace(/^file:\/\//, ""))
    readonly property var filtered: accounts.filter(function (a) {
        return a.name.toLocaleLowerCase().indexOf(search.text.toLocaleLowerCase()) !== -1;
    })
    readonly property var chosen: accountList.currentIndex >= 0 && accountList.currentIndex < filtered.length ? filtered[accountList.currentIndex] : null

    function tr(key) {
        return I18n.text(key, root.language);
    }
    function open(payloadJson) {
        root.opened = true;
        root.page = "list";
        root.pageHistory = [];
        root.message = "";
        root.errorCode = "";
        search.text = "";
        clearSecrets();
        backend.running = true;
        Qt.callLater(function () {
            search.forceActiveFocus();
        });
    }
    function close() {
        if (root.busy)
            return;
        fileDialog.close();
        root.opened = false;
        root.pasteToken = "";
        root.pageHistory = [];
        backend.running = false;
        root.accounts = [];
        previewModel.clear();
        root.previewToken = "";
        confirmation.opened = false;
        root.confirmCallback = null;
        clearSecrets();
    }
    function dismiss() {
        root.close();
        if (!root.opened && root.shell && typeof root.shell.hide === "function")
            root.shell.hide("kuryrc.mfa");
    }
    function toggle() {
        if (root.opened)
            root.dismiss();
        else
            root.open("{}");
    }
    function clearSecrets() {
        secretInput.text = "";
        urlInput.text = "";
    }
    function rpc(request, callback, background) {
        if (!backend.running || root.busy)
            return;
        root.backgroundRefresh = Boolean(background);
        root.busy = true;
        request.id = ++root.serial;
        root.pending[request.id] = callback;
        backend.write(JSON.stringify(request) + "\n");
    }
    function receive(line) {
        var reply;
        try {
            reply = JSON.parse(line);
            if (!reply || typeof reply.id !== "number" || !Object.prototype.hasOwnProperty.call(root.pending, reply.id) || typeof reply.ok !== "boolean" || (reply.ok && (!reply.data || typeof reply.data !== "object" || Array.isArray(reply.data))) || (!reply.ok && typeof reply.error !== "string"))
                throw new Error("Invalid backend reply");
        } catch (_) {
            root.pending = ({});
            root.busy = false;
            root.pasteToken = "";
            root.errorCode = "backend_failed";
            root.message = root.tr("backend_failed");
            backend.running = false;
            return;
        }
        var callback = root.pending[reply.id];
        delete root.pending[reply.id];
        root.busy = false;
        if (!root.opened)
            return;
        if (!reply.ok) {
            root.pasteToken = "";
            root.errorCode = reply.error;
            root.message = root.tr(reply.error);
            if (reply.error.indexOf("keyring") === 0 || reply.error === "invalid_vault")
                root.accounts = [];
            if (reply.error === "name_conflict" && (root.page === "add" || root.page === "url")) {
                root.ask(root.tr("overwriteConfirm"), function () {
                    root.saveAccount(true);
                });
            }
            return;
        }
        root.errorCode = "";
        if (callback)
            callback(reply.data);
    }
    function update(data) {
        if (data.accounts !== undefined)
            root.accounts = data.accounts;
        if (data.settings !== undefined)
            root.settings = data.settings;
        if (data.revision)
            root.vaultRevision = data.revision;
        if (accountList.currentIndex >= root.filtered.length)
            accountList.currentIndex = Math.max(0, root.filtered.length - 1);
    }
    function refresh(background) {
        root.rpc({
            op: "list"
        }, function (data) {
            root.update(data);
        }, background !== false);
    }
    function moveSelection(direction) {
        var view = root.page === "list" ? accountList : root.page === "actions" ? actionsList : root.page === "preview" ? previewList : null;
        if (!view)
            return false;
        if ((!root.busy || root.backgroundRefresh) && view.count > 0) {
            var next = view.currentIndex + direction;
            view.currentIndex = root.page === "list" ? (next + view.count) % view.count : Math.max(0, Math.min(view.count - 1, next));
            view.positionViewAtIndex(view.currentIndex, ListView.Contain);
        }
        return true;
    }
    function go(page, returning) {
        if (page === "list")
            root.pageHistory = [];
        else if (page !== root.page && !returning)
            root.pageHistory = root.pageHistory.concat([root.page]);
        root.page = page;
        root.message = "";
        root.errorCode = "";
        if (page !== "add" && page !== "url")
            clearSecrets();
        Qt.callLater(function () {
            if (page === "list")
                search.forceActiveFocus();
            else if (page === "actions")
                actionsList.forceActiveFocus();
            else if (page === "add" || page === "rename")
                nameInput.forceActiveFocus();
            else if (page === "url")
                urlInput.forceActiveFocus();
            else if (page === "import")
                sourceInput.forceActiveFocus();
            else if (page === "preview")
                previewList.forceActiveFocus();
            else
                keyRoot.forceActiveFocus();
        });
    }
    function goBack() {
        if (root.busy && !root.backgroundRefresh)
            return;
        if (root.page === "list")
            root.dismiss();
        else {
            if (root.page === "preview") {
                root.rpc({
                    op: "cancel_preview"
                }, function () {});
                previewModel.clear();
                root.previewToken = "";
            }
            var history = root.pageHistory.slice();
            var previousPage = history.length ? history.pop() : "list";
            root.pageHistory = history;
            root.go(previousPage, true);
        }
    }
    function ask(message, callback) {
        root.confirmCallback = callback;
        confirmation.message = message;
        confirmation.selectedIndex = 0;
        confirmation.opened = true;
        keyRoot.forceActiveFocus();
    }
    function finishCopy(data) {
        if (data.pasteToken)
            root.pasteToken = data.pasteToken;
        else
            root.dismiss();
    }
    function pasteAfterHidden() {
        if (panel.visible || !root.opened || !root.pasteToken)
            return;
        root.rpc({
            op: "paste",
            token: root.pasteToken
        }, function () {
            root.dismiss();
        });
    }
    function activate(other) {
        if (!root.chosen || root.busy)
            return;
        var paste = root.settings.defaultAction === "paste";
        if (other)
            paste = !paste;
        root.rpc({
            op: "copy",
            accountId: root.chosen.id,
            paste: paste
        }, root.finishCopy);
    }
    function runAction(action) {
        if (root.busy)
            return;
        var account = root.chosen;
        if (action === "copy" || action === "paste") {
            if (account)
                root.rpc({
                    op: "copy",
                    accountId: account.id,
                    paste: action === "paste"
                }, root.finishCopy);
        } else if (action === "add" || action === "rename") {
            root.selectedAccountId = account ? account.id : "";
            nameInput.text = action === "rename" && account ? account.name : "";
            secretInput.text = "";
            algorithmInput.value = "SHA1";
            digitsInput.value = "6";
            periodInput.text = "30";
            root.go(action);
        } else if (action === "remove") {
            if (account)
                root.ask(root.tr("deleteConfirm") + "\n" + account.name, function () {
                    root.rpc({
                        op: "delete",
                        accountId: account.id,
                        revision: root.vaultRevision
                    }, function (data) {
                        root.update(data);
                        root.go("list");
                    });
                });
        } else if (action === "addUrl") {
            root.go("url");
        } else if (action === "restore") {
            sourceInput.text = "";
            root.go("import");
        } else if (action === "backup") {
            root.ask(root.tr("exportConfirm"), function () {
                root.rpc({
                    op: "export",
                    confirmed: true
                }, function (data) {
                    root.go("list");
                    root.message = root.tr("exported") + data.path;
                });
            });
        } else if (action === "settings") {
            languageInput.value = root.settings.language;
            defaultActionInput.value = root.settings.defaultAction;
            root.go("settings");
        }
    }
    function saveAccount(overwrite) {
        var request = {
            op: root.page === "rename" ? "rename" : "add",
            revision: root.vaultRevision,
            overwrite: overwrite
        };
        if (root.page === "rename") {
            request.accountId = root.selectedAccountId;
            request.name = nameInput.text;
        } else if (root.page === "url")
            request.uri = urlInput.text;
        else
            request.account = {
                name: nameInput.text,
                secret: secretInput.text,
                algorithm: algorithmInput.value,
                digits: digitsInput.value,
                period: periodInput.text
            };
        root.rpc(request, function (data) {
            root.update(data);
            root.go("list");
        });
    }
    function previewImport() {
        root.rpc({
            op: "preview",
            path: sourceInput.text
        }, function (data) {
            root.previewToken = data.token;
            previewModel.clear();
            for (var i = 0; i < data.rows.length; i++) {
                var row = data.rows[i];
                row.checked = !row.error && !row.conflict;
                previewModel.append(row);
            }
            root.go("preview");
        });
    }
    function commitImport() {
        var selections = [];
        for (var i = 0; i < previewModel.count; i++) {
            var row = previewModel.get(i);
            if (row.checked)
                selections.push({
                    index: row.index,
                    overwrite: row.conflict
                });
        }
        if (!selections.length) {
            root.message = root.tr("nothing_selected");
            return;
        }
        root.ask(root.tr("importConfirm"), function () {
            root.rpc({
                op: "import",
                token: root.previewToken,
                selections: selections
            }, function (data) {
                root.update(data);
                root.go("list");
                var result = data.result;
                root.message = root.tr("addedCount") + " " + result.added + " · " + root.tr("overwrittenCount") + " " + result.overwritten + " · " + root.tr("skippedCount") + " " + result.skipped + " · " + root.tr("invalidCount") + " " + result.invalid;
                previewModel.clear();
            });
        });
    }

    Process {
        id: backend
        command: ["/usr/bin/python3", "-B", "-u", root.backendPath]
        stdinEnabled: true
        onStarted: root.refresh(false)
        stdout: SplitParser {
            onRead: function (line) {
                root.receive(line);
            }
        }
        // Do not forward process output or request payloads into the shell log.
        stderr: StdioCollector {}
        onExited: {
            root.pending = ({});
            root.busy = false;
            root.pasteToken = "";
            if (root.opened) {
                root.accounts = [];
                root.errorCode = "backend_failed";
                root.message = root.tr("backend_failed");
            }
        }
    }
    Timer {
        interval: 250
        repeat: true
        running: root.opened && !root.pasteToken
        onTriggered: {
            var previous = root.now;
            root.now = Date.now() / 1000;
            if (root.page === "list" && !root.busy && !root.errorCode && Math.floor(root.now) !== Math.floor(previous))
                root.refresh();
        }
    }
    ListModel {
        id: previewModel
    }

    FileDialog {
        id: fileDialog
        title: root.tr("path")
        fileMode: FileDialog.OpenFile
        // Keep file pickers in the panel. Native GTK dialogs have crashed the
        // shared shell process; a layer-shell panel is not a native dialog parent.
        options: FileDialog.DontUseNativeDialog
        parentWindow: keyRoot.Window.window
        popupType: Controls.Popup.Item
        onAccepted: {
            sourceInput.text = decodeURIComponent(selectedFile.toString().replace(/^file:\/\//, ""));
            sourceInput.forceActiveFocus();
        }
        onRejected: sourceInput.forceActiveFocus()
    }
    PanelWindow {
        id: panel
        visible: root.opened && !root.pasteToken
        // Dispatch only after the surface is hidden and Qt has processed that change.
        onVisibleChanged: {
            if (!visible)
                Qt.callLater(root.pasteAfterHidden);
        }
        anchors {
            top: true
            bottom: true
            left: true
            right: true
        }
        exclusionMode: ExclusionMode.Ignore
        color: "transparent"
        WlrLayershell.namespace: "omarchy-mfa"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

        Rectangle {
            anchors.fill: parent
            color: Color.menu.scrim
        }
        MouseArea {
            anchors.fill: parent
            onClicked: root.dismiss()
        }
        Ui.BorderSurface {
            id: card
            anchors.centerIn: parent
            width: Math.min(Style.space(760), panel.width - Style.gapsOut * 2)
            height: Math.min(Style.space(590), panel.height - Style.gapsOut * 2)
            radius: Style.cornerRadius
            color: Color.menu.background
            borderSpec: Border.surfaceSpec("menu", "border", Color.menu.border, Math.max(1, Style.space(2)))
            MouseArea {
                anchors.fill: parent
                onClicked: {}
            }

            Item {
                id: keyRoot
                anchors.fill: parent
                anchors.margins: Style.spacing.panelPadding
                Keys.priority: Keys.BeforeItem
                Keys.onPressed: function (event) {
                    if (confirmation.opened) {
                        confirmation.handleKey(event);
                        event.accepted = true;
                        return;
                    }
                    if (event.key === Qt.Key_Escape) {
                        root.goBack();
                        event.accepted = true;
                        return;
                    }
                    var ctrl = event.modifiers & Qt.ControlModifier;
                    var shift = event.modifiers & Qt.ShiftModifier;
                    if (ctrl && !shift && (event.key === Qt.Key_P || event.key === Qt.Key_N) && root.moveSelection(event.key === Qt.Key_N ? 1 : -1)) {
                        event.accepted = true;
                        return;
                    }
                    if (ctrl && event.key === Qt.Key_K) {
                        if (!root.busy || root.backgroundRefresh) {
                            if (root.page === "actions")
                                root.goBack();
                            else
                                root.go("actions");
                        }
                        event.accepted = true;
                        return;
                    }
                    if (root.busy)
                        return;
                    if (ctrl && shift && event.key === Qt.Key_N && (root.page === "list" || root.page === "actions")) {
                        root.runAction("add");
                        event.accepted = true;
                        return;
                    }
                    if (root.page === "list") {
                        if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
                            root.moveSelection(event.key === Qt.Key_Down ? 1 : -1);
                            event.accepted = true;
                        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                            root.activate(Boolean(event.modifiers & Qt.ShiftModifier));
                            event.accepted = true;
                        } else if (ctrl && event.key === Qt.Key_U) {
                            root.runAction("addUrl");
                            event.accepted = true;
                        } else if (ctrl && event.key === Qt.Key_E && root.chosen) {
                            root.runAction("rename");
                            event.accepted = true;
                        }
                    }
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: Style.spacing.md
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "MFA"
                            color: Color.menu.text
                            font.family: Style.font.menuFamily
                            font.pixelSize: Style.font.title
                            font.bold: true
                        }
                        Text {
                            text: root.page === "list" ? "" : root.tr(root.page === "url" ? "addUrl" : root.page === "import" ? "restore" : root.page)
                            color: Color.menu.text
                            opacity: 0.6
                            font.pixelSize: Style.font.body
                            Layout.fillWidth: true
                            textFormat: Text.PlainText
                        }
                        Item {
                            Layout.fillWidth: root.page === "list"
                        }
                        Ui.Button {
                            text: root.page === "list" ? root.tr("actions") + "  Ctrl+k" : root.tr("back")
                            focusable: true
                            enabled: !root.busy
                            onClicked: root.page === "list" ? root.go("actions") : root.goBack()
                        }
                    }

                    Ui.TextField {
                        id: search
                        Layout.fillWidth: true
                        visible: root.page === "list"
                        placeholderText: root.tr("search")
                        // TextInput uses Ctrl+K to delete text; handle overlay keys first.
                        Keys.priority: Keys.BeforeItem
                        Keys.forwardTo: [keyRoot]
                        onTextChanged: accountList.currentIndex = 0
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: root.page === "list"
                        ListView {
                            id: accountList
                            anchors.fill: parent
                            clip: true
                            spacing: Style.spacing.xs
                            model: root.filtered
                            currentIndex: 0
                            onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                            delegate: Rectangle {
                                required property var modelData
                                required property int index
                                width: accountList.width
                                height: Style.space(72)
                                radius: Style.cornerRadius
                                color: accountList.currentIndex === index ? Color.menu.selectedBackground : "transparent"
                                readonly property real remaining: Math.max(0, Math.ceil(modelData.expiresAt - root.now))
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: Style.spacing.md
                                    spacing: Style.spacing.lg
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: Style.spacing.xs
                                        Text {
                                            text: modelData.name
                                            textFormat: Text.PlainText
                                            color: Color.menu.text
                                            font.family: Style.font.menuFamily
                                            font.pixelSize: Style.font.body
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                        Text {
                                            text: modelData.algorithm + " · " + modelData.period + "s"
                                            color: Color.menu.text
                                            opacity: 0.45
                                            font.pixelSize: Style.font.caption
                                        }
                                    }
                                    Text {
                                        text: remaining > 0 ? modelData.code : "······"
                                        textFormat: Text.PlainText
                                        color: Color.menu.selectedText
                                        font.family: Style.font.family
                                        font.pixelSize: Style.font.title
                                        font.letterSpacing: Style.space(3)
                                    }
                                    Column {
                                        Layout.preferredWidth: Style.space(48)
                                        spacing: Style.spacing.xs
                                        Text {
                                            text: remaining + "s"
                                            color: Color.menu.text
                                            opacity: 0.65
                                            font.pixelSize: Style.font.caption
                                        }
                                        Rectangle {
                                            width: parent.width
                                            height: Style.space(3)
                                            color: Qt.rgba(Color.menu.text.r, Color.menu.text.g, Color.menu.text.b, 0.12)
                                            Rectangle {
                                                width: parent.width * Math.min(1, remaining / modelData.period)
                                                height: parent.height
                                                color: Color.menu.selectedText
                                            }
                                        }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onEntered: accountList.currentIndex = index
                                    onClicked: {
                                        accountList.currentIndex = index;
                                        root.activate(false);
                                    }
                                }
                            }
                        }
                        Column {
                            anchors.centerIn: parent
                            width: parent.width
                            spacing: Style.spacing.lg
                            visible: !root.filtered.length && !root.errorCode
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: root.accounts.length ? root.tr("noMatches") : root.tr("empty")
                                color: Color.menu.text
                                font.pixelSize: Style.font.title
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: root.accounts.length ? "" : root.tr("emptyHint")
                                color: Color.menu.text
                                opacity: 0.6
                                font.pixelSize: Style.font.body
                            }
                            Row {
                                anchors.horizontalCenter: parent.horizontalCenter
                                spacing: Style.spacing.md
                                visible: !root.accounts.length
                                Ui.Button {
                                    text: root.tr("add")
                                    bordered: true
                                    focusable: true
                                    enabled: !root.busy
                                    onClicked: root.runAction("add")
                                }
                                Ui.Button {
                                    text: root.tr("addUrl")
                                    bordered: true
                                    focusable: true
                                    enabled: !root.busy
                                    onClicked: root.runAction("addUrl")
                                }
                            }
                        }
                    }

                    ListView {
                        id: actionsList
                        property real pointerX: -1
                        property real pointerY: -1
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        visible: root.page === "actions"
                        model: (root.chosen ? ["copy", "paste", "rename", "remove"] : []).concat(["add", "addUrl", "restore", "backup", "settings"])
                        spacing: Style.spacing.xs
                        highlightMoveDuration: 0
                        highlightResizeDuration: 0
                        // One shared highlight follows selection, including mouse navigation.
                        highlight: Ui.BorderSurface {
                            color: Style.hoverFillFor(Color.foreground, Color.accent)
                            borderSpec: Border.controlSpec("hover-cursor", Color.foreground, Color.accent)
                            radius: Style.cornerRadius
                        }
                        Keys.onReturnPressed: root.runAction(model[currentIndex])
                        Keys.onEnterPressed: root.runAction(model[currentIndex])
                        delegate: Ui.Button {
                            required property string modelData
                            required property int index
                            width: actionsList.width
                            height: Style.space(38)
                            leftAlign: true
                            // ListView focuses this delegate; Button gates Enter on focusable.
                            focusable: true
                            text: root.tr(modelData)
                            hasCursor: actionsList.currentIndex === index
                            // Delegate hover/focus must not paint a second selection.
                            color: "transparent"
                            borderSpec: Border.none()
                            enabled: !root.busy
                            onActiveFocusChanged: {
                                if (activeFocus)
                                    actionsList.currentIndex = index;
                            }
                            onClicked: root.runAction(modelData)
                            MouseArea {
                                anchors.fill: parent
                                hoverEnabled: true
                                acceptedButtons: Qt.NoButton
                                onPositionChanged: function (mouse) {
                                    var point = mapToItem(actionsList, mouse.x, mouse.y);
                                    // Ignore hover events caused by showing the menu again.
                                    if (point.x === actionsList.pointerX && point.y === actionsList.pointerY)
                                        return;
                                    actionsList.pointerX = point.x;
                                    actionsList.pointerY = point.y;
                                    actionsList.currentIndex = index;
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        visible: root.page === "add" || root.page === "rename"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: Style.spacing.md
                        Text {
                            text: root.tr("name")
                            color: Color.menu.text
                            font.pixelSize: Style.font.body
                        }
                        Ui.TextField {
                            id: nameInput
                            Layout.fillWidth: true
                            maximumLength: 256
                            placeholderText: "GitHub"
                            onAccepted: if (root.page === "rename")
                                root.saveAccount(false)
                        }
                        Text {
                            visible: root.page === "add"
                            text: root.tr("secret")
                            color: Color.menu.text
                            font.pixelSize: Style.font.body
                        }
                        Ui.TextField {
                            id: secretInput
                            visible: root.page === "add"
                            Layout.fillWidth: true
                            password: true
                            maximumLength: 4096
                        }
                        RowLayout {
                            visible: root.page === "add"
                            Layout.fillWidth: true
                            spacing: Style.spacing.md
                            Ui.Dropdown {
                                id: algorithmInput
                                Layout.fillWidth: true
                                label: root.tr("algorithm")
                                value: "SHA1"
                                options: ["SHA1", "SHA256", "SHA512"]
                                onChanged: function (value) {
                                    algorithmInput.value = value;
                                }
                            }
                            Ui.Dropdown {
                                id: digitsInput
                                Layout.fillWidth: true
                                label: root.tr("digits")
                                value: "6"
                                options: ["6", "7", "8"]
                                onChanged: function (value) {
                                    digitsInput.value = value;
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Text {
                                    text: root.tr("period")
                                    color: Color.menu.text
                                    font.pixelSize: Style.font.caption
                                }
                                Ui.TextField {
                                    id: periodInput
                                    text: "30"
                                    Layout.fillWidth: true
                                    validator: IntValidator {
                                        bottom: 1
                                    }
                                    inputMethodHints: Qt.ImhDigitsOnly
                                }
                            }
                        }
                        Item {
                            Layout.fillHeight: true
                        }
                        Ui.Button {
                            text: root.tr("save")
                            bordered: true
                            focusable: true
                            enabled: !root.busy
                            onClicked: root.saveAccount(false)
                        }
                    }

                    ColumnLayout {
                        visible: root.page === "url"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Ui.TextField {
                            id: urlInput
                            Layout.fillWidth: true
                            placeholderText: root.tr("url")
                            password: true
                            maximumLength: 8192
                            onAccepted: root.saveAccount(false)
                        }
                        Item {
                            Layout.fillHeight: true
                        }
                        Ui.Button {
                            text: root.tr("save")
                            bordered: true
                            focusable: true
                            enabled: !root.busy
                            onClicked: root.saveAccount(false)
                        }
                    }

                    ColumnLayout {
                        visible: root.page === "import"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: Style.spacing.md
                        Text {
                            text: root.tr("importHint")
                            color: Color.menu.text
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Ui.TextField {
                                id: sourceInput
                                Layout.fillWidth: true
                                placeholderText: root.tr("path")
                                onAccepted: root.previewImport()
                            }
                            Ui.Button {
                                text: root.tr("browse")
                                bordered: true
                                focusable: true
                                onClicked: fileDialog.open()
                            }
                        }
                        Item {
                            Layout.fillHeight: true
                        }
                        Ui.Button {
                            text: root.tr("preview")
                            bordered: true
                            focusable: true
                            enabled: !root.busy && sourceInput.text.length > 0
                            onClicked: root.previewImport()
                        }
                    }

                    ColumnLayout {
                        visible: root.page === "preview"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: Style.spacing.md
                        Text {
                            text: root.tr("previewHint")
                            color: Color.menu.text
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        ListView {
                            id: previewList
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            model: previewModel
                            spacing: Style.spacing.xs
                            Keys.onSpacePressed: if (currentIndex >= 0 && !previewModel.get(currentIndex).error)
                                previewModel.setProperty(currentIndex, "checked", !previewModel.get(currentIndex).checked)
                            delegate: Ui.Button {
                                required property int index
                                required property string name
                                required property string error
                                required property int row
                                required property bool conflict
                                required property bool checked
                                focusable: true
                                width: previewList.width
                                height: Style.space(62)
                                leftAlign: true
                                hasCursor: previewList.currentIndex === index
                                selected: checked
                                onActiveFocusChanged: if (activeFocus)
                                    previewList.currentIndex = index
                                text: (error ? "! " : checked ? "☑ " : "☐ ") + (name || root.tr("line") + " " + row) + "\n" + (error ? root.tr(error) : checked ? root.tr(conflict ? "overwrite" : "importOne") : root.tr("skip"))
                                onClicked: {
                                    previewList.currentIndex = index;
                                    if (!error)
                                        previewModel.setProperty(index, "checked", !checked);
                                }
                            }
                        }
                        Ui.Button {
                            text: root.tr("importSelected")
                            bordered: true
                            focusable: true
                            enabled: !root.busy
                            onClicked: root.commitImport()
                        }
                    }

                    ColumnLayout {
                        visible: root.page === "settings"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: Style.spacing.lg
                        Ui.Dropdown {
                            id: languageInput
                            Layout.fillWidth: true
                            label: root.tr("language")
                            options: [
                                {
                                    value: "auto",
                                    label: root.tr("auto")
                                },
                                {
                                    value: "en",
                                    label: "English"
                                },
                                {
                                    value: "zh",
                                    label: "简体中文"
                                }
                            ]
                            onChanged: function (value) {
                                languageInput.value = value;
                            }
                        }
                        Ui.Dropdown {
                            id: defaultActionInput
                            Layout.fillWidth: true
                            label: root.tr("defaultAction")
                            options: [
                                {
                                    value: "copy",
                                    label: root.tr("copy")
                                },
                                {
                                    value: "paste",
                                    label: root.tr("paste")
                                }
                            ]
                            onChanged: function (value) {
                                defaultActionInput.value = value;
                            }
                        }
                        Text {
                            text: root.tr("settingsHint")
                            color: Color.menu.text
                            opacity: 0.65
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Item {
                            Layout.fillHeight: true
                        }
                        Ui.Button {
                            text: root.tr("save")
                            bordered: true
                            focusable: true
                            enabled: !root.busy
                            onClicked: root.rpc({
                                op: "settings",
                                revision: root.vaultRevision,
                                settings: {
                                    language: languageInput.value,
                                    defaultAction: defaultActionInput.value
                                }
                            }, function (data) {
                                root.update(data);
                                root.go("list");
                            })
                        }
                    }

                    Text {
                        text: root.message || (root.busy && !root.backgroundRefresh ? root.tr("loading") : "")
                        visible: text.length > 0
                        textFormat: Text.PlainText
                        color: root.errorCode ? "#e78284" : Color.menu.text
                        wrapMode: Text.WrapAnywhere
                        Layout.fillWidth: true
                        font.pixelSize: Style.font.caption
                    }
                    RowLayout {
                        visible: root.errorCode.length > 0
                        Ui.Button {
                            text: root.tr(root.errorCode === "keyring_locked" ? "unlock" : "retry")
                            bordered: true
                            focusable: true
                            enabled: !root.busy
                            onClicked: {
                                root.message = "";
                                if (!backend.running)
                                    backend.running = true;
                                else
                                    root.rpc({
                                        op: root.errorCode === "keyring_locked" ? "unlock" : "list"
                                    }, function (data) {
                                        root.update(data);
                                    });
                            }
                        }
                    }
                    Text {
                        visible: root.page === "list" || root.page === "actions"
                        text: root.tr(root.page === "actions" ? "actionsHelp" : "listHelp")
                        color: Color.menu.text
                        opacity: 0.4
                        font.pixelSize: Style.font.caption
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }
            }
            Ui.ConfirmDialog {
                id: confirmation
                anchors.fill: parent
                background: Color.menu.background
                foreground: Color.menu.text
                selectedText: Color.menu.selectedText
                cancelText: root.tr("cancel")
                confirmText: root.tr("confirm")
                onCanceled: {
                    confirmation.opened = false;
                    root.confirmCallback = null;
                    root.go(root.page);
                }
                onConfirmed: {
                    confirmation.opened = false;
                    var callback = root.confirmCallback;
                    root.confirmCallback = null;
                    if (callback)
                        callback();
                }
            }
        }
    }
}

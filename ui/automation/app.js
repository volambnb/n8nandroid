(function () {
  "use strict";

  const EDGE_LABELS = ["next", "true", "false", "error", "loop", "break", "fallback", "success"];
  const SELECT_OPTIONS = {
    selector_type: ["css", "xpath", "text"],
    method: ["GET", "POST", "PUT", "DELETE", "PATCH"],
    response_type: ["json", "raw"],
    mode: ["fixed", "random", "count", "list", "while", "get", "update", "append", "overwrite"],
    action: ["export", "import", "copy", "paste", "read"],
    output_type: ["text", "image"],
    email_service: ["gmail", "hotmail", "yahoo", "custom"],
    file_type: ["file", "base64", "url image"],
    operation: ["read", "write"],
    frame: ["main", "custom"],
    action_for_dialog: ["yes", "no"],
    save_asset_by: ["url", "selector"],
    wait_for_navigation: ["load", "domcontentloaded", "networkidle0", "networkidle2"],
    wait_state: ["visible", "attached", "hidden", "detached"],
    select_option_by: ["value", "label", "index"],
  };
  const LONG_TEXT_KEYS = [
    "script",
    "expression",
    "content",
    "text",
    "prompt",
    "body",
    "headers",
    "params",
    "row",
    "cases",
    "input_base64_image",
  ];
  const VARIABLE_CONSTANTS = [
    { label: "PROFILE_ID", key: "profile_id" },
    { label: "PROFILE_NAME", key: "profile_name" },
    { label: "PHONE_SERIAL", key: "phone_serial" },
    { label: "PHONE_CONNECTION", key: "phone_connection" },
  ];
  const FIELD_LABELS = {
    name: "Tên",
    title: "Tiêu đề",
    text: "Nội dung văn bản",
    value: "Giá trị",
    username: "Tên đăng nhập",
    password: "Mật khẩu",
    email: "Email",
    method: "Phương thức",
    action: "Thao tác",
    operation: "Tác vụ",
    headers: "Header HTTP",
    params: "Tham số",
    body: "Nội dung gửi đi",
    payload: "Dữ liệu gửi đi",
    content: "Nội dung",
    prompt: "Chỉ dẫn",
    expression: "Biểu thức",
    script: "Mã lệnh",
    code: "Mã lệnh",
    enabled: "Bật tính năng",
    retries: "Số lần thử lại",
    max_retries: "Số lần thử tối đa",
    max_auto_retries: "Số lần thử lại an toàn tối đa",
    retry_delay: "Thời gian giữa các lần thử (giây)",
    include_phone_context: "Đọc thêm trạng thái phone",
    condition: "Điều kiện",
    output: "Đầu ra",
    input: "Đầu vào",
    source: "Nguồn",
    destination: "Đích",
    group_id: "ID nhóm",
    tag_id: "ID thẻ",
    row: "Dữ liệu hàng",
    cases: "Các trường hợp",
    save_asset_by: "Lưu tài nguyên theo",
    url: "Địa chỉ URL",
    selector: "Bộ chọn phần tử",
    selector_type: "Loại bộ chọn",
    output_variable: "Biến đầu ra",
    serial_variable: "Biến kết nối phone",
    timeout: "Thời gian chờ (giây)",
    wait_for_navigation: "Chờ trang tải",
    wait_time_ms: "Thời gian chờ thêm (mili giây)",
    navigation_timeout_seconds: "Giới hạn tải trang (giây)",
    wait_state: "Trạng thái cần chờ",
    file_path: "Đường dẫn tệp hoặc dữ liệu",
    file_type: "Loại tệp",
    filename: "Tên tệp",
    option_value: "Giá trị lựa chọn",
    option_label: "Nhãn lựa chọn",
    option_index: "Vị trí lựa chọn",
    select_option_by: "Chọn theo",
    sleep_before_run_seconds: "Chờ trước khi chạy node (giây, 0 để bỏ qua)",
  };
  const DEFAULT_FIELD_HINTS = {
    url: "URL đích cần mở. Ví dụ: https://example.com",
    selector: "Selector mục tiêu để thao tác với element.",
    selector_type: "Chọn đúng kiểu selector bạn đang dùng.",
    output_variable: "Tên biến lưu output để dùng cho node sau.",
    serial_variable: "Mặc định artemis_phone. Khi chạy riêng node, autoIXB lấy lại phone còn online của đúng profile.",
    timeout: "Thời gian chờ tối đa trước khi node fail.",
    wait_for_navigation: "Điều kiện trang được xem là tải xong.",
    wait_time_ms: "Chờ thêm sau khi load xong để trang ổn định.",
    navigation_timeout_seconds: "Thời gian tối đa cho lệnh mở URL.",
    wait_state: "Trạng thái element cần đợi trước khi trả kết quả.",
    file_path: "Đường dẫn file local hoặc dữ liệu theo loại file upload.",
    file_type: "Chọn nguồn upload: file, base64, hoặc URL image.",
    filename: "Tên file gửi lên khi dùng base64 hoặc URL.",
    option_value: "Giá trị `value` của option cần chọn.",
    option_label: "Nội dung hiển thị (text/label) của option cần chọn.",
    option_index: "Vị trí option theo index, bắt đầu từ 0.",
    select_option_by: "Chọn cách xác định option trong dropdown.",
    sleep_before_run_seconds: "Node sẽ chờ số giây này trước khi thực thi. Đặt 0 để tắt.",
  };
  const UI_TEXT_VI = {
    "Open URL options": "Tùy chọn mở URL",
    "Element Exist options": "Tùy chọn kiểm tra phần tử",
    "Get Text options": "Tùy chọn đọc văn bản",
    "Get Value options": "Tùy chọn đọc giá trị",
    "Select Dropdown options": "Tùy chọn chọn danh sách",
    "File Upload options": "Tùy chọn tải tệp",
    "Analyze Error": "Phân tích lỗi node",
    "Nhận lỗi qua cổng error của node trước đó; kết quả nằm trong biến đầu ra.": "Nối cổng error của node cần theo dõi vào node này. Kết quả gồm loại lỗi, nguyên nhân có thể và bước khắc phục.",
    "Chỉ bật khi cần đối chiếu selector với cây Accessibility hiện tại. Không ghi nội dung màn hình vào log.": "Chỉ bật khi cần đối chiếu selector với cây Accessibility hiện tại. Node chỉ lưu số lượng phần tử khớp, không ghi chữ trên màn hình vào log.",
    "Chỉ đề xuất thử lại lỗi tạm thời ở node đọc dữ liệu. Muốn thử lại, nối cổng true về node lỗi; cổng false đi tới Log/recovery/Stop. Click, nhập, cài app và thao tác ghi không được tự lặp.": "Chỉ đề xuất thử lại lỗi tạm thời ở node đọc dữ liệu. Nối cổng true về node lỗi; cổng false tới Log, recovery hoặc Stop. Node không tự lặp click, nhập, cài app hay thao tác có thể tạo tác động.",
    "Branch behavior": "Cách rẽ nhánh",
    "Extraction settings": "Cài đặt trích xuất",
    "Read settings": "Cài đặt đọc dữ liệu",
    "Select settings": "Cài đặt lựa chọn",
    "Upload settings": "Cài đặt tải tệp",
    "Click options": "Tùy chọn nhấp",
    "Execution settings": "Cài đặt thực thi",
    "Typing settings": "Cài đặt nhập văn bản",
    "Node note": "Ghi chú node",
    "Selector type": "Loại bộ chọn",
    Selector: "Bộ chọn phần tử",
    "Wait time (milliseconds)": "Thời gian chờ thêm (mili giây)",
    "Wait for navigation": "Chờ trang tải",
    "Wait state": "Trạng thái cần chờ",
    "Timeout (seconds)": "Thời gian chờ (giây)",
    "Output variable": "Biến đầu ra",
    "Trim whitespace": "Xóa khoảng trắng thừa",
    "Select option by": "Chọn theo",
    "Option index": "Vị trí lựa chọn",
    "Option label": "Nhãn lựa chọn",
    "Option value": "Giá trị lựa chọn",
    "File type": "Loại tệp",
    "Base64 data": "Dữ liệu Base64",
    Filename: "Tên tệp",
    "Image URL": "URL hình ảnh",
    "File path": "Đường dẫn tệp",
    Button: "Nút chuột",
    "Select by": "Chọn phần tử theo",
    "Click count": "Số lần nhấp",
    "Force click": "Bắt buộc nhấp",
    "Type into": "Nhập vào",
    "Input strategy": "Cách nhập",
    Text: "Văn bản",
    "Delay (ms)": "Độ trễ (mili giây)",
    Note: "Ghi chú",
    "Sleep time (seconds) before run this node (0 to disable)": "Chờ trước khi chạy node (giây, 0 để bỏ qua)",
    "XPath selector. Ví dụ: //button[contains(.,'Login')]": "Bộ chọn XPath. Ví dụ: //button[contains(.,'Login')]",
    "Text selector. Ví dụ: Login hoặc Sign in": "Bộ chọn theo chữ. Ví dụ: Login hoặc Sign in",
    "CSS selector. Ví dụ: button.login hoặc input[name='email']": "Bộ chọn CSS. Ví dụ: button.login hoặc input[name='email']",
    "Active page mode: text sẽ gõ vào vị trí con trỏ hiện tại.": "Chế độ trang hiện tại: văn bản sẽ được nhập tại vị trí con trỏ.",
    "Tìm thấy element => đi theo edge `true`; không thấy => edge `false`.": "Tìm thấy phần tử thì đi theo nhánh `true`; nếu không, đi theo nhánh `false`.",
    "Biến output sẽ là boolean: true/false.": "Biến đầu ra có giá trị đúng hoặc sai.",
  };

  const state = {
    token: "",
    catalog: [],
    defaultsByType: {},
    apps: [],
    tasks: [],
    currentAppId: null,
    currentRunId: null,
    selectedNodeId: null,
    nodes: [],
    edges: [],
    inputs: [],
    loadedProfiles: [],
    selectedProfileIds: [],
    profilePickerLoading: false,
    profileListPage: 1,
    profilePageSize: 12,
    currentRunStatus: "",
    runStopRequested: false,
    canvasZoom: 1,
    runningSingleNodeId: null,
    runActiveNodeId: null,
    runFailedNodeIds: new Set(),
    runNodeStepIndices: new Map(),
    runStepCounter: 0,
    runPollTimer: null,
    runDiscoveryTimer: null,
    runDiscoverySince: 0,
    inspectorTabByNodeId: {},
    openNodePropertiesId: null,
    nodeDraft: null,
    dragNodeId: null,
    dragOffset: { x: 0, y: 0 },
    canvasPan: null,
    dragFrameId: 0,
    pendingDragPosition: null,
    connectDraft: {
      active: false,
      fromNodeId: null,
      fromLabel: "next",
      mouseX: 0,
      mouseY: 0,
    },
    extensionsConfig: null,
    extensionsSaving: false,
    appEditorView: "home",
    openAppIds: [],
    activeMainTab: "automation",
    ixProfiles: [],
    ixOpenedProfileIds: new Set(),
    ixProfilesPage: 1,
    ixProfilesTotal: 0,
    ixProxies: [],
    ixProxiesPage: 1,
    ixProxiesTotal: 0,
    ixSelectedProxy: null,
    phoneAssets: [],
    phoneAssetUrls: new Map(),
    phoneDevices: [],
    phoneRecording: null,
    phoneRecorderEpoch: 0,
    phoneFrame: null,
    phoneCropFrame: null,
    phoneCropMode: false,
    phonePointerStart: null,
    phoneStreamController: null,
    phoneStreamRetryTimer: null,
    phoneStreamWatchdog: null,
    phoneStreamGeneration: 0,
    phoneStreamLastAt: 0,
    phoneStreamRetryMs: 1000,
    phoneFrameRequest: null,
    phoneActionInFlight: false,
    phoneMatchPreview: null,
  };

  const els = {
    apiToken: byId("apiToken"),
    appName: byId("appName"),
    appDesc: byId("appDesc"),
    appHome: byId("appHome"),
    appHomeTabs: byId("appHomeTabs"),
    appEditorTabs: byId("appEditorTabs"),
    appHomeRecent: byId("appHomeRecent"),
    appHomeEmpty: byId("appHomeEmpty"),
    appHomeSearch: byId("appHomeSearch"),
    builderLayout: byId("builderLayout"),
    appVersion: byId("appVersion"),
    taskList: byId("taskList"),
    runAppBtn: byId("runAppBtn"),
    runAppStopBtn: byId("runAppStopBtn"),
    runAppIcon: byId("runAppIcon"),
    runAppLabel: byId("runAppLabel"),
    appRunInputs: byId("appRunInputs"),
    runLogs: byId("runLogs"),
    runDock: byId("runDock"),
    canvasWorld: byId("canvasWorld"),
    canvasZoomLabel: byId("canvasZoomLabel"),
    canvasZoomOutBtn: byId("canvasZoomOutBtn"),
    canvasZoomInBtn: byId("canvasZoomInBtn"),
    canvasZoomFitBtn: byId("canvasZoomFitBtn"),
    taskName: byId("taskName"),
    canvas: byId("canvas"),
    edgeLayer: byId("edgeLayer"),
    palette: byId("palette"),
    nodeMeta: byId("nodeMeta"),
    nodeForm: byId("nodeForm"),
    nodePropertiesDialog: byId("nodePropertiesDialog"),
    nodeDialogTitle: byId("nodeDialogTitle"),
    nodeDialogIcon: byId("nodeDialogIcon"),
    saveNodeBtn: byId("saveNodeBtn"),
    cancelNodeBtn: byId("cancelNodeBtn"),
    nodeConfigEditor: byId("nodeConfigEditor"),
    newConfigKey: byId("newConfigKey"),
    newConfigValue: byId("newConfigValue"),
    edgeList: byId("edgeList"),
    loadProfilesBtn: byId("loadProfilesBtn"),
    reloadProfilesBtn: byId("reloadProfilesBtn"),
    profilePicker: byId("profilePicker"),
    profileSearch: byId("profileSearch"),
    profilePickerList: byId("profilePickerList"),
    selectAllProfilesBtn: byId("selectAllProfilesBtn"),
    clearProfileSelectionBtn: byId("clearProfileSelectionBtn"),
    profilePrevPageBtn: byId("profilePrevPageBtn"),
    profileNextPageBtn: byId("profileNextPageBtn"),
    profilePageLabel: byId("profilePageLabel"),
    profilePageSize: byId("profilePageSize"),
    selectedProfilesSummary: byId("selectedProfilesSummary"),
    profileIds: byId("profileIds"),
    groupId: byId("groupId"),
    tagId: byId("tagId"),
    edgeLabelSelect: byId("edgeLabelSelect"),
    toast: byId("toast"),
    refreshExtensionsBtn: byId("refreshExtensionsBtn"),
    uploadExtensionBtn: byId("uploadExtensionBtn"),
    importUrlExtensionBtn: byId("importUrlExtensionBtn"),
    extensionFileInput: byId("extensionFileInput"),
    extLoadEnabled: byId("extLoadEnabled"),
    extDisableWelcome: byId("extDisableWelcome"),
    extDisableOther: byId("extDisableOther"),
    extensionPathInput: byId("extensionPathInput"),
    addPathExtensionBtn: byId("addPathExtensionBtn"),
    extensionStartupArgs: byId("extensionStartupArgs"),
    extensionList: byId("extensionList"),
    workspaceTitle: byId("workspaceTitle"),
    workspaceSubtitle: byId("workspaceSubtitle"),
    automationWorkspace: byId("automationWorkspace"),
    createProfileWorkspace: byId("createProfileWorkspace"),
    profilesWorkspace: byId("profilesWorkspace"),
    proxyWorkspace: byId("proxyWorkspace"),
    createProfileRefreshMetaBtn: byId("createProfileRefreshMetaBtn"),
    createProfileSubmitBtn: byId("createProfileSubmitBtn"),
    createProfileForm: byId("createProfileForm"),
    createProfileResult: byId("createProfileResult"),
    profilesRefreshBtn: byId("profilesRefreshBtn"),
    profilesRefreshBtnSide: byId("profilesRefreshBtnSide"),
    profilesKeyword: byId("profilesKeyword"),
    profilesGroupId: byId("profilesGroupId"),
    profilesTagId: byId("profilesTagId"),
    profilesLimit: byId("profilesLimit"),
    profilesPrevBtn: byId("profilesPrevBtn"),
    profilesNextBtn: byId("profilesNextBtn"),
    profilesPageLabel: byId("profilesPageLabel"),
    profilesTable: byId("profilesTable"),
    proxiesRefreshBtn: byId("proxiesRefreshBtn"),
    proxiesRefreshBtnSide: byId("proxiesRefreshBtnSide"),
    proxyForm: byId("proxyForm"),
    proxySaveBtn: byId("proxySaveBtn"),
    proxyResetBtn: byId("proxyResetBtn"),
    proxyAssignBtn: byId("proxyAssignBtn"),
    proxiesSearch: byId("proxiesSearch"),
    proxiesMode: byId("proxiesMode"),
    proxiesTagId: byId("proxiesTagId"),
    proxiesLimit: byId("proxiesLimit"),
    proxiesPrevBtn: byId("proxiesPrevBtn"),
    proxiesNextBtn: byId("proxiesNextBtn"),
    proxiesPageLabel: byId("proxiesPageLabel"),
    proxiesTable: byId("proxiesTable"),
    workspacePanel: byId("workspacePanel"),
    workspacePanelToggle: byId("workspacePanelToggle"),
    workspaceScrim: byId("workspaceScrim"),
    appShell: document.querySelector(".app-shell"),
    phoneRecorderDialog: byId("phoneRecorderDialog"),
    phoneRecorderStatus: byId("phoneRecorderStatus"),
    phoneRecorderSerial: byId("phoneRecorderSerial"),
    phoneRecorderPreview: byId("phoneRecorderPreview"),
    phoneRecorderImage: byId("phoneRecorderImage"),
    phoneRecorderBackdrop: byId("phoneRecorderBackdrop"),
    phoneRecorderTouchLayer: byId("phoneRecorderTouchLayer"),
    phoneRecorderResolution: byId("phoneRecorderResolution"),
    phoneRecorderStreamStatus: byId("phoneRecorderStreamStatus"),
    phoneRecorderEvents: byId("phoneRecorderEvents"),
    phoneRecorderSegments: byId("phoneRecorderSegments"),
    phoneRecorderCropRect: byId("phoneRecorderCropRect"),
    phoneRecorderMatchRect: byId("phoneRecorderMatchRect"),
  };

  boot().catch((err) => {
    console.error(err);
    toast("Startup failed: " + err.message, true);
  });

  async function boot() {
    bindEvents();
    state.token = localStorage.getItem("automation_token") || "";
    els.apiToken.value = state.token;
    try {
      const openIds = JSON.parse(localStorage.getItem("ix_app_editor_tabs") || "[]");
      state.openAppIds = Array.isArray(openIds) ? openIds.map(String).slice(-6) : [];
    } catch {
      state.openAppIds = [];
    }
    const savedProfilePageSize = Number(localStorage.getItem("automation_profile_page_size") || 12);
    state.profilePageSize = clampProfilePageSize(savedProfilePageSize);
    els.profilePageSize.value = String(state.profilePageSize);
    await bootstrapData();
    await loadPhoneAssets().catch((err) => console.warn("Phone image assets could not be loaded", err));
    renderExtensionsSection();
    newGraph();
    setAppEditorView("home");
    syncSelectedProfilesToInput();
    renderProfilePickerList();
    switchMainTab(localStorage.getItem("ix_main_tab") || "automation", { persist: false });
  }

  function bindEvents() {
    els.workspacePanelToggle.addEventListener("click", () => {
      setWorkspacePanel(els.workspacePanel.classList.contains("is-open") === false);
    });
    els.workspaceScrim.addEventListener("click", () => setWorkspacePanel(false));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && els.workspacePanel.classList.contains("is-open")) {
        setWorkspacePanel(false);
        els.workspacePanelToggle.focus();
      }
    });
    byId("newAppHomeBtn").addEventListener("click", startNewApp);
    byId("newAppEmptyBtn").addEventListener("click", startNewApp);
    byId("backToAppsBtn").addEventListener("click", requestAppHome);
    const saveAppPrompt = byId("saveAppPrompt");
    const discardAppAndGoHomeBtn = byId("discardAppAndGoHomeBtn");
    const saveAppAndGoHomeBtn = byId("saveAppAndGoHomeBtn");
    saveAppPrompt.addEventListener("cancel", (event) => event.preventDefault());
    discardAppAndGoHomeBtn.addEventListener("click", () => {
      saveAppPrompt.close();
      newGraph();
      returnToAppHome();
    });
    saveAppAndGoHomeBtn.addEventListener("click", async () => {
      saveAppAndGoHomeBtn.disabled = true;
      discardAppAndGoHomeBtn.disabled = true;
      try {
        const saved = await saveApp();
        if (saved) {
          saveAppPrompt.close();
          returnToAppHome();
        }
      } catch (err) {
        toast("Không lưu được ứng dụng: " + err.message, true);
      } finally {
        saveAppAndGoHomeBtn.disabled = false;
        discardAppAndGoHomeBtn.disabled = false;
      }
    });
    byId("focusAppNameBtn").addEventListener("click", () => {
      els.appName.focus();
      els.appName.select();
    });
    els.appHomeSearch.addEventListener("input", renderAppHome);
    byId("saveAppBtn").addEventListener("click", saveApp);
    byId("deleteAppBtn").addEventListener("click", deleteCurrentApp);
    byId("saveTaskBtn").addEventListener("click", saveTask);
    byId("refreshTasksBtn").addEventListener("click", refreshTasks);
    els.runAppBtn.addEventListener("click", runCurrentApp);
    els.runAppStopBtn.addEventListener("click", stopCurrentRun);
    byId("refreshRunsBtn").addEventListener("click", refreshCurrentRunLog);
    byId("stopRunBtn").addEventListener("click", stopCurrentRun);
    byId("clearCanvasBtn").addEventListener("click", clearCanvas);
    els.canvasZoomOutBtn.addEventListener("click", () => setCanvasZoom(state.canvasZoom - 0.1));
    els.canvasZoomInBtn.addEventListener("click", () => setCanvasZoom(state.canvasZoom + 0.1));
    els.canvasZoomFitBtn.addEventListener("click", fitCanvasToNodes);
    byId("applyNodeConfigBtn").addEventListener("click", applyNodeConfig);
    els.saveNodeBtn.addEventListener("click", saveNodeProperties);
    els.cancelNodeBtn.addEventListener("click", closeNodeProperties);
    byId("removeNodeBtn").addEventListener("click", removeSelectedNode);
    byId("closeNodePropertiesBtn").addEventListener("click", closeNodeProperties);
    els.nodePropertiesDialog.addEventListener("click", (event) => {
      if (event.target === els.nodePropertiesDialog) closeNodeProperties();
    });
    els.nodePropertiesDialog.addEventListener("close", () => {
      state.openNodePropertiesId = null;
      state.nodeDraft = null;
    });
    byId("exportGraphBtn").addEventListener("click", exportGraph);
    byId("exportBundleBtn").addEventListener("click", exportAppBundle);
    byId("importBundleBtn").addEventListener("click", () => byId("importBundleFile").click());
    byId("importBundleFile").addEventListener("change", () => importAppBundle().catch((err) => toast("Không nhập được gói app: " + err.message, true)));
    byId("openPhoneRecorderBtn").addEventListener("click", () => openPhoneRecorder().catch((err) => toast(err.message, true)));
    byId("closePhoneRecorderBtn").addEventListener("click", () => els.phoneRecorderDialog.close());
    byId("refreshPhoneDevicesBtn").addEventListener("click", () => reloadPhoneDevices().catch((err) => toast(err.message, true)));
    els.phoneRecorderSerial.addEventListener("change", () => changePhoneRecorderDevice().catch((err) => toast(err.message, true)));
    byId("startPhoneRecordingBtn").addEventListener("click", () => startOrResumePhoneRecording().catch((err) => toast(err.message, true)));
    byId("pausePhoneRecordingBtn").addEventListener("click", () => pausePhoneRecording().catch((err) => toast(err.message, true)));
    byId("markPhoneSegmentBtn").addEventListener("click", () => markPhoneSegment().catch((err) => toast(err.message, true)));
    byId("finishPhoneRecordingBtn").addEventListener("click", () => finishPhoneRecording().catch((err) => toast(err.message, true)));
    byId("generatePhoneAppsBtn").addEventListener("click", () => generatePhoneApps().catch((err) => toast(err.message, true)));
    byId("deletePhoneDraftBtn").addEventListener("click", () => deletePhoneDraft().catch((err) => toast(err.message, true)));
    byId("phoneRecorderCropBtn").addEventListener("click", () => {
      if (!state.phoneCropMode) state.phoneCropEventIndex = null;
      togglePhoneCropMode().catch((err) => toast(err.message, true));
    });
    byId("phoneRecorderTypeBtn").addEventListener("click", () => typePhoneText().catch((err) => toast(err.message, true)));
    byId("phoneRecorderEnterBtn").addEventListener("click", () => recordPhoneAction({ type: "press_key", key: "ENTER" }).catch((err) => toast(err.message, true)));
    byId("phoneRecorderText").addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      (async () => {
        await typePhoneText();
        await recordPhoneAction({ type: "press_key", key: "ENTER" });
      })().catch((err) => toast(err.message, true));
    });
    byId("phoneRecorderBackBtn").addEventListener("click", () => recordPhoneAction({ type: "press_key", key: "BACK" }).catch((err) => toast(err.message, true)));
    byId("phoneRecorderHomeBtn").addEventListener("click", () => recordPhoneAction({ type: "press_key", key: "HOME" }).catch((err) => toast(err.message, true)));
    els.phoneRecorderImage.addEventListener("pointerdown", onPhonePreviewPointerDown);
    els.phoneRecorderImage.addEventListener("pointerup", (event) => onPhonePreviewPointerUp(event).catch((err) => toast(err.message, true)));
    els.phoneRecorderImage.addEventListener("pointermove", onPhonePreviewPointerMove);
    els.phoneRecorderImage.addEventListener("pointercancel", () => { state.phonePointerStart = null; });
    els.phoneRecorderDialog.addEventListener("close", () => {
      clearPhoneRecorderSession();
    });
    byId("addConfigFieldBtn").addEventListener("click", addConfigField);
    els.loadProfilesBtn.addEventListener("click", () => {
      loadProfilesForPicker().catch((err) => toast("Load profiles failed: " + err.message, true));
    });
    els.reloadProfilesBtn.addEventListener("click", (e) => {
      e.preventDefault();
      loadProfilesForPicker().catch((err) => toast("Reload profiles failed: " + err.message, true));
    });
    els.profileSearch.addEventListener("input", () => {
      state.profileListPage = 1;
      renderProfilePickerList();
    });
    els.selectAllProfilesBtn.addEventListener("click", (e) => {
      e.preventDefault();
      selectAllVisibleProfiles();
    });
    els.clearProfileSelectionBtn.addEventListener("click", (e) => {
      e.preventDefault();
      clearProfileSelection();
    });
    els.profilePrevPageBtn.addEventListener("click", (e) => {
      e.preventDefault();
      changeProfilePage(-1);
    });
    els.profileNextPageBtn.addEventListener("click", (e) => {
      e.preventDefault();
      changeProfilePage(1);
    });
    els.profilePageSize.addEventListener("change", () => {
      updateProfilePageSize(els.profilePageSize.value);
    });
    els.profilePageSize.addEventListener("input", () => {
      updateProfilePageSize(els.profilePageSize.value);
    });
    els.groupId.addEventListener("change", () => {
      syncSelectedProfilesToInput();
    });
    els.tagId.addEventListener("change", () => {
      syncSelectedProfilesToInput();
    });
    els.refreshExtensionsBtn.addEventListener("click", () => {
      loadExtensionConfig().catch((err) => toast("Reload extensions failed: " + err.message, true));
    });
    els.uploadExtensionBtn.addEventListener("click", () => {
      els.extensionFileInput.click();
    });
    els.extensionFileInput.addEventListener("change", () => {
      handleExtensionUpload().catch((err) => toast("Upload extension failed: " + err.message, true));
    });
    els.importUrlExtensionBtn.addEventListener("click", () => {
      importExtensionFromUrl().catch((err) => toast("Import URL failed: " + err.message, true));
    });
    els.extLoadEnabled.addEventListener("change", () => {
      updateExtensionFlag("load_extensions", els.extLoadEnabled.checked);
    });
    els.extDisableWelcome.addEventListener("change", () => {
      updateExtensionFlag("disable_extension_welcome_page", els.extDisableWelcome.checked);
    });
    els.extDisableOther.addEventListener("change", () => {
      updateExtensionFlag("disable_other_extensions", els.extDisableOther.checked);
    });
    els.addPathExtensionBtn.addEventListener("click", () => {
      addPathExtension().catch((err) => toast("Add path extension failed: " + err.message, true));
    });
    els.extensionStartupArgs.addEventListener("change", () => {
      saveStartupArgs().catch((err) => toast("Save startup args failed: " + err.message, true));
    });
    document.addEventListener("click", (event) => {
      if (!els.profilePicker.open) return;
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (!els.profilePicker.contains(target)) {
        els.profilePicker.open = false;
      }
    });

    els.apiToken.addEventListener("change", () => {
      state.token = els.apiToken.value.trim();
      localStorage.setItem("automation_token", state.token);
      toast("Token updated");
      bootstrapData().catch((err) => toast("Reload failed: " + err.message, true));
    });

    document.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });
    document.querySelectorAll("[data-main-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetTab = btn.dataset.mainTab || "automation";
        if (targetTab === "automation" && state.activeMainTab === "automation" && state.appEditorView === "editor") {
          requestAppHome();
          return;
        }
        switchMainTab(targetTab);
      });
    });

    els.createProfileRefreshMetaBtn.addEventListener("click", () => {
      loadIxMetadata().catch((err) => toast("Reload metadata failed: " + err.message, true));
    });
    const profileProxyMode = byId("profileProxyMode");
    const syncProfileProxyFields = () => {
      const mode = profileProxyMode.value || "direct";
      document.querySelectorAll("[data-profile-proxy-mode]").forEach((field) => {
        field.hidden = field.dataset.profileProxyMode !== mode;
      });
      byId("profileProxyDirectHelp").hidden = mode !== "direct";
    };
    profileProxyMode.addEventListener("change", syncProfileProxyFields);
    syncProfileProxyFields();
    els.createProfileSubmitBtn.addEventListener("click", () => {
      createIxProfile().catch((err) => toast("Create profile failed: " + err.message, true));
    });
    els.createProfileForm.addEventListener("submit", (e) => {
      e.preventDefault();
      createIxProfile().catch((err) => toast("Create profile failed: " + err.message, true));
    });
    [els.profilesRefreshBtn, els.profilesRefreshBtnSide].forEach((btn) => {
      btn.addEventListener("click", () => refreshIxProfiles().catch((err) => toast("Reload profiles failed: " + err.message, true)));
    });
    [els.profilesKeyword, els.profilesGroupId, els.profilesTagId, els.profilesLimit].forEach((el) => {
      el.addEventListener("change", () => {
        state.ixProfilesPage = 1;
        refreshIxProfiles().catch((err) => toast("Reload profiles failed: " + err.message, true));
      });
    });
    els.profilesKeyword.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        state.ixProfilesPage = 1;
        refreshIxProfiles().catch((err) => toast("Reload profiles failed: " + err.message, true));
      }
    });
    els.profilesPrevBtn.addEventListener("click", () => changeIxProfilesPage(-1));
    els.profilesNextBtn.addEventListener("click", () => changeIxProfilesPage(1));

    [els.proxiesRefreshBtn, els.proxiesRefreshBtnSide].forEach((btn) => {
      btn.addEventListener("click", () => refreshIxProxies().catch((err) => toast("Reload proxies failed: " + err.message, true)));
    });
    [els.proxiesMode, els.proxiesTagId, els.proxiesLimit].forEach((el) => {
      el.addEventListener("change", () => {
        state.ixProxiesPage = 1;
        refreshIxProxies().catch((err) => toast("Reload proxies failed: " + err.message, true));
      });
    });
    els.proxiesSearch.addEventListener("input", renderIxProxies);
    els.proxiesPrevBtn.addEventListener("click", () => changeIxProxiesPage(-1));
    els.proxiesNextBtn.addEventListener("click", () => changeIxProxiesPage(1));
    els.proxyForm.addEventListener("submit", (e) => {
      e.preventDefault();
      saveIxProxy().catch((err) => toast("Save proxy failed: " + err.message, true));
    });
    els.proxyResetBtn.addEventListener("click", resetProxyForm);
    els.proxyAssignBtn.addEventListener("click", () => assignProxyToSelectedProfiles().catch((err) => toast("Assign proxy failed: " + err.message, true)));

    els.canvas.addEventListener("dragover", (e) => e.preventDefault());
    els.canvas.addEventListener("drop", onDropNode);
    els.canvas.addEventListener("mousedown", onCanvasMouseDown);
    els.canvas.addEventListener("mousemove", onCanvasMouseMove);

    window.addEventListener("mousemove", onDragMove);
    window.addEventListener("mouseup", onWindowMouseUp);
    window.addEventListener("blur", onWindowMouseUp);
    window.addEventListener("resize", () => {
      updateCanvasBounds();
      drawEdges();
    });
  }

  async function bootstrapData() {
    try {
      await Promise.all([
        loadCatalog(),
        refreshApps(),
        refreshTasks(),
        loadExtensionConfig(),
      ]);
    } catch (err) {
      console.error(err);
      toast("Enter Bearer Token if API auth is enabled.", true);
    }
  }

  async function api(path, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    if (state.token) {
      headers.Authorization = `Bearer ${state.token}`;
    }
    const res = await fetch(path, Object.assign({}, options, { headers }));
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        msg = body.detail || body.message || msg;
      } catch (_) {}
      throw new Error(msg);
    }
    const ctype = res.headers.get("content-type") || "";
    if (ctype.includes("application/json")) {
      return res.json();
    }
    return res.text();
  }

  async function loadPhoneAssets() {
    state.phoneAssets = await api("/automation/phone/assets");
    return state.phoneAssets;
  }

  async function loadPhoneDevices() {
    const result = await api("/automation/phone/devices");
    state.phoneDevices = Array.isArray(result.devices) ? result.devices : [];
    const onlineDevices = state.phoneDevices.filter((device) => device.state === "device");
    const recordingSerial = String(state.phoneRecording?.serial || "");
    const savedSerial = String(localStorage.getItem("autoixb_phone_serial") || "");
    const onlineSerials = new Set(onlineDevices.map((device) => device.serial));
    const recordingDeviceOnline = onlineSerials.has(recordingSerial);
    const preferred = recordingDeviceOnline
      ? recordingSerial
      : (recordingSerial && onlineDevices.length > 1
        ? ""
        : (onlineSerials.has(savedSerial) && savedSerial !== recordingSerial
        ? savedSerial
        : (onlineDevices.length === 1 ? onlineDevices[0].serial : "")));
    els.phoneRecorderSerial.replaceChildren();
    if (state.phoneRecording && recordingSerial && !recordingDeviceOnline && onlineDevices.length > 1) {
      const choose = document.createElement("option");
      choose.value = "";
      choose.textContent = "Chọn phone online để đổi thiết bị ghi";
      choose.selected = true;
      els.phoneRecorderSerial.appendChild(choose);
    }
    if (state.phoneRecording && recordingSerial && !recordingDeviceOnline) {
      const old = document.createElement("option");
      old.value = recordingSerial;
      old.textContent = `${recordingSerial} · phiên cũ không còn online (bản nháp vẫn được giữ)`;
      old.disabled = true;
      old.selected = !preferred && onlineDevices.length === 0;
      els.phoneRecorderSerial.appendChild(old);
    }
    if (!state.phoneDevices.length) {
      const option = document.createElement("option"); option.value = ""; option.textContent = "Không tìm thấy thiết bị ADB"; els.phoneRecorderSerial.appendChild(option);
    }
    state.phoneDevices.forEach((device) => {
      const option = document.createElement("option"); option.value = device.serial;
      option.textContent = `${device.serial} · ${device.state}${device.details ? ` · ${device.details}` : ""}`;
      option.disabled = device.state !== "device";
      option.selected = device.serial === preferred;
      els.phoneRecorderSerial.appendChild(option);
    });
    renderPhoneRecorderState();
    return state.phoneDevices;
  }

  async function reloadPhoneDevices() {
    stopPhoneFrameStreaming();
    await loadPhoneDevices();
    if (!state.phoneRecording) return;
    try {
      const boundDeviceOnline = state.phoneDevices.some((device) => device.serial === state.phoneRecording.serial && device.state === "device");
      if (!boundDeviceOnline) { setPhoneStreamStatus("Phone chưa kết nối", "error"); renderPhoneRecorderState(); return; }
      await refreshPhoneFrame(true);
      startPhoneFrameStreaming();
      renderPhoneRecorderState();
    } catch (err) {
      els.phoneRecorderStatus.textContent = `Không đọc được màn hình phone: ${err.message}`;
      setPhoneStreamStatus(`Lỗi ảnh: ${err.message}`, "error");
    }
  }

  async function changePhoneRecorderDevice() {
    stopPhoneFrameStreaming();
    const recording = state.phoneRecording;
    const serial = String(els.phoneRecorderSerial.value || "").trim();
    const selected = state.phoneDevices.find((device) => device.serial === serial && device.state === "device");
    if (!recording || !selected || recording.serial === serial) return;
    if (recording.status === "recording") return;
    clearPhoneRecorderSession();
    localStorage.setItem("autoixb_phone_serial", serial);
    els.phoneRecorderSerial.value = serial;
    renderPhoneRecorderState();
    toast("Đã chọn phone khác. Bấm Bắt đầu ghi để tạo phiên mới, không ghép thao tác cũ.");
  }

  function clearPhoneRecorderSession() {
    const previous = state.phoneRecording;
    state.phoneRecorderEpoch += 1;
    stopPhoneFrameStreaming();
    if (previous?.status === "recording") {
      api(`/automation/phone/recordings/${encodeURIComponent(previous.id)}/status`, {
        method: "PUT", body: JSON.stringify({ status: "paused" }),
      }).catch((err) => console.warn("Could not pause the previous phone recording:", err));
    }
    state.phoneRecording = null;
    state.phoneFrame = null;
    state.phoneFrameRequest = null;
    state.phoneCropFrame = null;
    state.phoneCropEventIndex = null;
    state.phoneCropMode = false;
    state.phonePointerStart = null;
    state.phoneMatchPreview = null;
    localStorage.removeItem("autoixb_phone_recording_id");
    els.phoneRecorderImage.removeAttribute("src");
    els.phoneRecorderBackdrop.removeAttribute("src");
    els.phoneRecorderPreview.style.removeProperty("aspect-ratio");
    els.phoneRecorderCropRect.hidden = true;
    els.phoneRecorderMatchRect.hidden = true;
    els.phoneRecorderResolution.textContent = "Chưa kết nối";
    byId("phoneRecorderCropBtn").textContent = "Cắt ảnh mẫu";
    byId("phoneRecorderText").value = "";
    byId("phoneRecorderSecret").checked = false;
    byId("phoneRecorderAppName").value = "Phone workflow";
    setPhoneStreamStatus("Chưa có phiên ghi");
    renderPhoneRecorderEvents();
    renderPhoneRecorderState();
  }

  async function openPhoneRecorder() {
    // Opening the recorder always starts with an empty draft. Pausing and
    // resuming are only available while this dialog remains open.
    clearPhoneRecorderSession();
    if (!els.phoneRecorderDialog.open) els.phoneRecorderDialog.showModal();
    els.phoneRecorderStatus.textContent = "Đang tải danh sách phone cho phiên mới…";
    try {
      await loadPhoneDevices();
    } catch (err) {
      els.phoneRecorderStatus.textContent = `Không tải được danh sách phone: ${err.message}`;
      throw err;
    }
    renderPhoneRecorderState();
  }

  async function startOrResumePhoneRecording() {
    stopPhoneFrameStreaming();
    const epoch = state.phoneRecorderEpoch;
    const serial = String(els.phoneRecorderSerial.value || "").trim();
    if (!serial) throw new Error("Chọn một ADB serial đã ở trạng thái device.");
    localStorage.setItem("autoixb_phone_serial", serial);
    if (state.phoneRecording?.status === "recording" && state.phoneRecording.serial !== serial) {
      throw new Error("Tạm dừng phiên hiện tại trước khi chọn phone khác.");
    }
    let recording;
    if (state.phoneRecording && state.phoneRecording.status !== "stopped" && state.phoneRecording.serial === serial) {
      recording = await api(`/automation/phone/recordings/${encodeURIComponent(state.phoneRecording.id)}/status`, { method: "PUT", body: JSON.stringify({ status: "recording" }) });
    } else {
      const created = await api("/automation/phone/recordings", { method: "POST", body: JSON.stringify({ serial }) });
      recording = await api(`/automation/phone/recordings/${encodeURIComponent(created.id)}`);
    }
    if (epoch !== state.phoneRecorderEpoch || !els.phoneRecorderDialog.open) {
      await api(`/automation/phone/recordings/${encodeURIComponent(recording.id)}/status`, {
        method: "PUT", body: JSON.stringify({ status: "paused" }),
      }).catch((err) => console.warn("Could not pause a closed phone recording:", err));
      return;
    }
    state.phoneRecording = recording;
    state.phoneFrame = null; state.phoneCropFrame = null; state.phoneCropEventIndex = null;
    state.phoneMatchPreview = null; els.phoneRecorderMatchRect.hidden = true;
    await refreshPhoneFrame();
    if (epoch !== state.phoneRecorderEpoch || !els.phoneRecorderDialog.open) return;
    startPhoneFrameStreaming();
    renderPhoneRecorderState(); renderPhoneRecorderEvents();
    toast(`Đang ghi thao tác trên ${serial}.`);
  }

  async function pausePhoneRecording() {
    if (!state.phoneRecording) return;
    const recordingId = state.phoneRecording.id;
    const updated = await api(`/automation/phone/recordings/${encodeURIComponent(recordingId)}/status`, { method: "PUT", body: JSON.stringify({ status: "paused" }) });
    if (state.phoneRecording?.id !== recordingId) return;
    state.phoneRecording = updated;
    renderPhoneRecorderState();
  }

  async function finishPhoneRecording() {
    if (!state.phoneRecording) return;
    const recordingId = state.phoneRecording.id;
    const updated = await api(`/automation/phone/recordings/${encodeURIComponent(recordingId)}/status`, { method: "PUT", body: JSON.stringify({ status: "stopped" }) });
    if (state.phoneRecording?.id !== recordingId) return;
    state.phoneRecording = updated;
    stopPhoneFrameStreaming();
    renderPhoneRecorderState(); renderPhoneRecorderEvents();
    toast("Đã kết thúc ghi. Bạn có thể tạo một app từ bản ghi.");
  }

  async function markPhoneSegment() {
    if (!state.phoneRecording) return;
    const name = prompt("Tên đoạn app con:", `Đoạn ${(state.phoneRecording.segments || []).length + 1}`);
    if (name == null) return;
    const segment = await api(`/automation/phone/recordings/${encodeURIComponent(state.phoneRecording.id)}/segments`, { method: "POST", body: JSON.stringify({ name }) });
    state.phoneRecording.segments = [...(state.phoneRecording.segments || []), segment];
    renderPhoneRecorderEvents();
  }

  async function generatePhoneApps() {
    if (!state.phoneRecording) return;
    const recordingId = state.phoneRecording.id;
    const epoch = state.phoneRecorderEpoch;
    if (state.phoneRecording.status !== "stopped") await finishPhoneRecording();
    if (state.phoneRecording?.id !== recordingId || epoch !== state.phoneRecorderEpoch) return;
    const result = await api(`/automation/phone/recordings/${encodeURIComponent(recordingId)}/generate`, {
      method: "POST", body: JSON.stringify({ name: byId("phoneRecorderAppName").value.trim() || "Phone workflow" }),
    });
    await refreshApps();
    if (epoch !== state.phoneRecorderEpoch) return;
    if (epoch === state.phoneRecorderEpoch && els.phoneRecorderDialog.open) els.phoneRecorderDialog.close();
    await selectApp((result.app || result.parent).id);
    toast("Đã tạo một app gồm kết nối phone và các thao tác đã ghi.");
  }

  async function deletePhoneDraft() {
    if (!state.phoneRecording || !confirm("Xóa bản nháp recorder này?")) return;
    const recordingId = state.phoneRecording.id;
    await api(`/automation/phone/recordings/${encodeURIComponent(recordingId)}`, { method: "DELETE" });
    if (state.phoneRecording?.id !== recordingId) return;
    state.phoneRecording = null;
    clearPhoneRecorderSession();
    await loadPhoneDevices();
  }

  function phoneFrameDataUrl(frame) {
    const mimeType = String(frame?.image_mime_type || "image/png").toLowerCase();
    const safeMimeType = ["image/png", "image/jpeg", "image/webp"].includes(mimeType) ? mimeType : "image/png";
    return `data:${safeMimeType};base64,${frame?.image_base64 || ""}`;
  }

  function displayPhoneRecorderFrame(frame) {
    const source = phoneFrameDataUrl(frame);
    const width = Number(frame?.width), height = Number(frame?.height);
    if (width > 0 && height > 0) els.phoneRecorderPreview.style.aspectRatio = `${width} / ${height}`;
    els.phoneRecorderImage.src = source;
    els.phoneRecorderBackdrop.src = source;
  }

  async function refreshPhoneFrame(allowStopped = false, forceFresh = false) {
    if (!state.phoneRecording || (state.phoneRecording.status === "stopped" && !allowStopped)) return;
    const recordingId = state.phoneRecording.id;
    if (state.phoneMatchPreview && !state.phoneCropMode) {
      state.phoneMatchPreview = null;
      els.phoneRecorderMatchRect.hidden = true;
    }
    if (state.phoneFrameRequest) {
      if (!forceFresh) return state.phoneFrameRequest;
      // A poll may have started before the tap/swipe and still be returning
      // its old frame. Wait for it to drain, then capture after the action.
      try { await state.phoneFrameRequest; } catch (_) {}
    }
    const request = (async () => {
      const frame = await api(`/automation/phone/recordings/${encodeURIComponent(recordingId)}/frame`, { method: "POST", body: JSON.stringify({}) });
      if (state.phoneRecording?.id !== recordingId) return frame;
      state.phoneFrame = frame;
      if (!state.phoneCropMode) {
        displayPhoneRecorderFrame(frame);
        els.phoneRecorderResolution.textContent = `${frame.width} × ${frame.height} · ${frame.backend || "ARTEMIS"} · ${frame.serial}`;
      }
      return frame;
    })();
    state.phoneFrameRequest = request;
    try { return await request; }
    finally { if (state.phoneFrameRequest === request) state.phoneFrameRequest = null; }
  }

  function phoneStreamCanRun() {
    return Boolean(els.phoneRecorderDialog.open && state.phoneRecording
      && state.phoneRecording.status !== "stopped" && !state.phoneCropMode
      && !state.phoneMatchPreview);
  }

  function setPhoneStreamStatus(message, kind = "") {
    els.phoneRecorderStreamStatus.textContent = message;
    els.phoneRecorderStreamStatus.classList.toggle("live", kind === "live");
    els.phoneRecorderStreamStatus.classList.toggle("error", kind === "error");
  }

  function stopPhoneFrameStreaming(resetRetry = true) {
    state.phoneStreamGeneration += 1;
    state.phoneStreamController?.abort();
    state.phoneStreamController = null;
    if (state.phoneStreamRetryTimer) window.clearTimeout(state.phoneStreamRetryTimer);
    if (state.phoneStreamWatchdog) window.clearInterval(state.phoneStreamWatchdog);
    state.phoneStreamRetryTimer = null;
    state.phoneStreamWatchdog = null;
    if (resetRetry) state.phoneStreamRetryMs = 1000;
  }

  async function consumePhoneFrameStream(generation, controller) {
    const recordingId = state.phoneRecording.id;
    const headers = state.token ? { Authorization: `Bearer ${state.token}` } : {};
    const response = await fetch(`/automation/phone/recordings/${encodeURIComponent(recordingId)}/stream`, {
      headers, signal: controller.signal, cache: "no-store",
    });
    if (!response.ok) throw new Error(`Luồng ảnh trả về HTTP ${response.status}`);
    if (!response.body) throw new Error("Trình duyệt không hỗ trợ đọc luồng ảnh.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      if (pending.length > 8 * 1024 * 1024) throw new Error("Frame phone vượt giới hạn 8 MiB.");
      let newline;
      while ((newline = pending.indexOf("\n")) !== -1) {
        const line = pending.slice(0, newline).trim();
        pending = pending.slice(newline + 1);
        if (!line || generation !== state.phoneStreamGeneration) continue;
        const message = JSON.parse(line);
        if (message.type === "error") throw new Error(message.message || "Không đọc được ảnh phone.");
        if (message.type !== "frame" || !message.frame) continue;
        const frame = message.frame;
        if (!phoneStreamCanRun() || frame.serial !== state.phoneRecording.serial
          || recordingId !== state.phoneRecording.id) continue;
        state.phoneStreamLastAt = Date.now();
        state.phoneStreamRetryMs = 1000;
        state.phoneFrame = frame;
        displayPhoneRecorderFrame(frame);
        els.phoneRecorderResolution.textContent = `${frame.width} × ${frame.height} · ${frame.backend || "ARTEMIS"} · ${frame.serial}`;
        setPhoneStreamStatus(`Trực tiếp · ${message.capture_ms || 0} ms/frame`, "live");
      }
    }
    if (generation === state.phoneStreamGeneration) throw new Error("Luồng ảnh phone đã ngắt.");
  }

  function startPhoneFrameStreaming(resetRetry = true) {
    stopPhoneFrameStreaming(resetRetry);
    if (!phoneStreamCanRun()) return;
    const generation = state.phoneStreamGeneration;
    const controller = new AbortController();
    state.phoneStreamController = controller;
    state.phoneStreamLastAt = Date.now();
    setPhoneStreamStatus("Đang kết nối ảnh…");
    state.phoneStreamWatchdog = window.setInterval(() => {
      if (generation === state.phoneStreamGeneration && Date.now() - state.phoneStreamLastAt > 8000) {
        controller.abort();
      }
    }, 1000);
    consumePhoneFrameStream(generation, controller).catch((err) => {
      if (generation !== state.phoneStreamGeneration) return;
      const delay = state.phoneStreamRetryMs;
      state.phoneStreamRetryMs = Math.min(delay * 2, 8000);
      setPhoneStreamStatus(`Mất luồng ảnh; nối lại sau ${delay / 1000}s`, "error");
      if (phoneStreamCanRun()) {
        state.phoneStreamRetryTimer = window.setTimeout(() => startPhoneFrameStreaming(false), delay);
      }
      console.warn("Phone preview stream interrupted:", err);
    });
  }

  function renderPhoneRecorderState() {
    const recording = state.phoneRecording;
    const status = String(recording?.status || "");
    const active = Boolean(recording && status !== "stopped");
    const isRecording = status === "recording";
    const isPaused = status === "paused";
    const device = state.phoneDevices.find((item) => item.serial === recording?.serial);
    const selectedDevice = state.phoneDevices.find((item) => item.serial === els.phoneRecorderSerial.value && item.state === "device");
    const boundDeviceOnline = Boolean(device && device.state === "device");
    byId("startPhoneRecordingBtn").textContent = isRecording ? "Đang ghi" : (isPaused && selectedDevice?.serial === recording?.serial ? "Tiếp tục ghi" : (recording ? "Ghi phiên mới" : "Bắt đầu ghi"));
    byId("startPhoneRecordingBtn").disabled = isRecording || !selectedDevice;
    byId("pausePhoneRecordingBtn").disabled = !isRecording;
    byId("pausePhoneRecordingBtn").textContent = "Tạm dừng";
    byId("markPhoneSegmentBtn").disabled = !isRecording || !(recording?.events?.length);
    byId("finishPhoneRecordingBtn").disabled = !active;
    byId("phoneRecorderCropBtn").disabled = !recording?.events?.length;
    byId("phoneRecorderTypeBtn").disabled = !isRecording;
    byId("phoneRecorderEnterBtn").disabled = !isRecording;
    byId("phoneRecorderBackBtn").disabled = !isRecording;
    byId("phoneRecorderHomeBtn").disabled = !isRecording;
    byId("generatePhoneAppsBtn").disabled = !(recording?.events?.length);
    byId("deletePhoneDraftBtn").disabled = !recording;
    els.phoneRecorderSerial.disabled = Boolean(recording && status === "recording");
    if (recording && status === "recording" && [...els.phoneRecorderSerial.options].some((option) => option.value === recording.serial)) {
      els.phoneRecorderSerial.value = recording.serial;
    }
    const model = String(device?.details || "").match(/(?:^|\s)model:([^\s]+)/i)?.[1];
    const deviceLabel = recording ? `${recording.serial}${model ? ` · ${model}` : ""}` : "";
    els.phoneRecorderStatus.textContent = recording
      ? (!boundDeviceOnline
        ? `Phone ${recording.serial} không còn online. ${selectedDevice ? `Bấm “Ghi phiên mới” cho ${selectedDevice.serial}.` : "Tải lại danh sách rồi chọn phone đang online."} Bản nháp cũ được giữ riêng trên máy.`
        : `${deviceLabel} · ${isRecording ? "Đang ghi" : (isPaused ? "Đã tạm dừng; bản nháp được lưu" : "Đã kết thúc; bản nháp vẫn còn")}`)
      : "Chọn đúng ADB serial của phone cần điều khiển.";
  }

  async function recordPhoneAction(action) {
    if (!state.phoneRecording || state.phoneRecording.status !== "recording") return;
    if (state.phoneActionInFlight) return;
    const recordingId = state.phoneRecording.id;
    state.phoneMatchPreview = null;
    els.phoneRecorderMatchRect.hidden = true;
    state.phoneActionInFlight = true;
    try {
      const result = await api(`/automation/phone/recordings/${encodeURIComponent(recordingId)}/actions`, { method: "POST", body: JSON.stringify(action) });
      if (state.phoneRecording?.id !== recordingId) return result;
      state.phoneRecording.events = [...(state.phoneRecording.events || []), result.event];
      if (["tap", "double_tap", "long_press"].includes(action.type)) {
        state.phoneCropFrame = { frame_id: result.before_frame_id, eventIndex: Number(result.event.index), ...result.before };
        state.phoneCropEventIndex = Number(result.event.index);
      }
      renderPhoneRecorderEvents(); renderPhoneRecorderState();
      // The live stream supplies the next image. An extra synchronous capture
      // here queued behind the stream and made every tap feel 2–3 seconds late.
      if (!state.phoneStreamController) startPhoneFrameStreaming();
      return result;
    } finally {
      state.phoneActionInFlight = false;
      if (!state.phoneStreamController && !state.phoneStreamRetryTimer) startPhoneFrameStreaming();
    }
  }

  async function typePhoneText() {
    const input = byId("phoneRecorderText");
    if (!input.value) return;
    if (state.phoneRecording?.status !== "recording") throw new Error("Bắt đầu hoặc tiếp tục ghi trước khi nhập chữ.");
    const recordingId = state.phoneRecording.id;
    const secret = byId("phoneRecorderSecret").checked;
    const variable = secret ? (prompt("Tên biến đầu vào bí mật:", `phone_secret_${(state.phoneRecording?.events || []).length + 1}`) || "") : "";
    if (secret && !variable.trim()) return;
    const result = await recordPhoneAction({ type: "send_text", value: input.value, secret, variable_name: variable.trim() });
    if (!result) throw new Error("Phone đang xử lý thao tác khác. Thử nhập lại sau khi thao tác trước hoàn tất.");
    if (state.phoneRecording?.id === recordingId) input.value = "";
  }

  function renderPhoneRecorderEvents() {
    const recording = state.phoneRecording;
    els.phoneRecorderEvents.replaceChildren(); els.phoneRecorderSegments.replaceChildren();
    (recording?.segments || []).forEach((segment, index) => {
      const item = document.createElement("div"); item.className = "phone-recorder-segment";
      item.textContent = `${index + 1}. ${segment.name} · bước ${segment.start_event}–${segment.end_event}`; els.phoneRecorderSegments.appendChild(item);
    });
    (recording?.events || []).forEach((event, index) => {
      const row = document.createElement("li"); row.className = "phone-recorder-event";
      const summary = document.createElement("span");
      const secretText = event.secret ? `biến ${event.text_variable || "nhạy cảm"}` : (event.type === "send_text" ? `“${event.text || ""}”` : "");
      const actionLabel = event.type === "send_text" ? "ARTEMIS Type Text" : event.type;
      summary.textContent = `${event.index || index + 1}. ${actionLabel}${secretText ? ` · ${secretText}` : ""}${event.selector?.value ? ` · selector ${event.selector.by}: ${event.selector.value}${event.selector_unique ? "" : " (không duy nhất)"}` : ""}`;
      row.appendChild(summary);
      if (event.image_asset_id) {
        const imagePreview = document.createElement("img"); imagePreview.className = "phone-recorder-event-image";
        imagePreview.alt = `Ảnh mẫu bước ${event.index || index + 1}`;
        phoneAssetUrl(event.image_asset_id).then((url) => { imagePreview.src = url; }).catch((err) => toast(err.message, true));
        row.appendChild(imagePreview);
        const matchBtn = document.createElement("button"); matchBtn.type = "button"; matchBtn.className = "ghost"; matchBtn.textContent = "Thử khớp";
        matchBtn.addEventListener("click", () => previewPhoneRecorderAsset(event.image_asset_id).catch((err) => toast(err.message, true)));
        row.appendChild(matchBtn);
      }
      if (["tap", "long_press", "double_tap"].includes(event.type)) {
        const cropBtn = document.createElement("button"); cropBtn.type = "button"; cropBtn.className = "ghost"; cropBtn.textContent = "Cắt lại";
        cropBtn.addEventListener("click", async () => {
          try {
            state.phoneCropEventIndex = Number(event.index || index + 1);
            state.phoneMatchPreview = null;
            els.phoneRecorderMatchRect.hidden = true;
            const frame = state.phoneCropFrame?.eventIndex === state.phoneCropEventIndex
              ? state.phoneCropFrame
              : await refreshPhoneFrame(true);
            if (!frame) throw new Error("Không lấy được ảnh phone để cắt lại.");
            state.phoneCropFrame = { ...frame, eventIndex: state.phoneCropEventIndex };
            state.phoneCropMode = false;
            await togglePhoneCropMode();
          } catch (err) { toast(err.message, true); }
        });
        row.appendChild(cropBtn);
      }
      els.phoneRecorderEvents.appendChild(row);
    });
    renderPhoneRecorderState();
  }

  async function previewPhoneRecorderAsset(assetId) {
    if (!state.phoneRecording) throw new Error("Chọn bản ghi phone trước.");
    stopPhoneFrameStreaming();
    let match;
    try { match = await api(`/automation/phone/assets/${encodeURIComponent(assetId)}/match`, {
      method: "POST",
      body: JSON.stringify({ serial: state.phoneRecording.serial, recording_id: state.phoneRecording.id,
        options: { threshold: 0.86, scale_min: 0.8, scale_max: 1.2, scale_steps: 9 } }),
    }); } catch (err) { startPhoneFrameStreaming(); throw err; }
    state.phoneMatchPreview = match;
    if (match.preview_image_base64 && match.frame_id) {
      state.phoneFrame = { frame_id: match.frame_id, serial: state.phoneRecording.serial, width: match.width,
        height: match.height, backend: "ARTEMIS", image_base64: match.preview_image_base64, image_mime_type: "image/png" };
      displayPhoneRecorderFrame(state.phoneFrame);
      els.phoneRecorderResolution.textContent = `${match.width} × ${match.height} · ARTEMIS · ${state.phoneRecording.serial}`;
    }
    if (match.found && !match.ambiguous && match.bbox && state.phoneFrame) {
      const image = els.phoneRecorderImage.getBoundingClientRect();
      const preview = byId("phoneRecorderPreview").getBoundingClientRect();
      const scaleX = image.width / match.width, scaleY = image.height / match.height;
      const box = match.bbox;
      Object.assign(els.phoneRecorderMatchRect.style, {
        left: `${image.left - preview.left + box.x * scaleX}px`,
        top: `${image.top - preview.top + box.y * scaleY}px`,
        width: `${box.w * scaleX}px`, height: `${box.h * scaleY}px`,
      });
      els.phoneRecorderMatchRect.hidden = false;
    } else {
      els.phoneRecorderMatchRect.hidden = true;
    }
    const message = match.ambiguous
      ? `Ảnh khớp nhiều vị trí gần tương đương (${(match.score * 100).toFixed(1)}%); sẽ không chạm.`
      : match.found
        ? `Khớp ${(match.score * 100).toFixed(1)}% · tâm ${match.center.x}, ${match.center.y}`
        : `Chưa khớp đủ ngưỡng · ${(match.score * 100).toFixed(1)}%`;
    els.phoneRecorderStatus.textContent = `${message} · chụp ${match.capture_ms} ms · tìm ${match.match_ms} ms`;
    return match;
  }

  async function togglePhoneCropMode() {
    state.phoneCropMode = !state.phoneCropMode;
    if (state.phoneCropMode) stopPhoneFrameStreaming();
    byId("phoneRecorderCropBtn").textContent = state.phoneCropMode ? "Hủy cắt ảnh" : "Cắt ảnh mẫu";
    els.phoneRecorderCropRect.hidden = true;
    if (state.phoneCropMode) {
      let source = state.phoneCropFrame || state.phoneFrame;
      try {
        if (!source && state.phoneRecording) source = await refreshPhoneFrame(true);
      } catch (err) {
        state.phoneCropMode = false; byId("phoneRecorderCropBtn").textContent = "Cắt ảnh mẫu";
        throw err;
      }
      if (!source) {
        state.phoneCropMode = false; byId("phoneRecorderCropBtn").textContent = "Cắt ảnh mẫu";
        throw new Error("Chụp frame phone trước.");
      }
      state.phoneCropFrame = source;
      displayPhoneRecorderFrame(source);
      els.phoneRecorderStatus.textContent = state.phoneCropEventIndex
        ? "Kéo trên ảnh phone để cắt lại vùng mẫu cho bước đã chọn."
        : "Kéo trên ảnh phone để cắt vùng mẫu từ frame gốc.";
    } else {
      state.phoneCropEventIndex = null;
      state.phoneCropFrame = null; state.phoneMatchPreview = null; els.phoneRecorderMatchRect.hidden = true;
      if (state.phoneFrame) displayPhoneRecorderFrame(state.phoneFrame);
      startPhoneFrameStreaming();
    }
  }

  function phonePreviewPoint(event) {
    const box = els.phoneRecorderImage.getBoundingClientRect();
    const parent = byId("phoneRecorderPreview").getBoundingClientRect();
    const drawnWidth = Math.max(1, box.width), drawnHeight = Math.max(1, box.height);
    const left = box.left, top = box.top;
    const x = (event.clientX - left) / drawnWidth, y = (event.clientY - top) / drawnHeight;
    return { x: Math.max(0, Math.min(1, x)), y: Math.max(0, Math.min(1, y)), inside: x >= 0 && x <= 1 && y >= 0 && y <= 1,
      rect: { left, top, width: drawnWidth, height: drawnHeight }, parent };
  }

  function showPhoneTouchRing(clientX, clientY) {
    const bounds = els.phoneRecorderPreview.getBoundingClientRect();
    const ring = document.createElement("span");
    ring.className = "phone-recorder-touch-ring";
    ring.style.left = `${clientX - bounds.left}px`;
    ring.style.top = `${clientY - bounds.top}px`;
    els.phoneRecorderTouchLayer.appendChild(ring);
    ring.addEventListener("animationend", () => ring.remove(), { once: true });
    window.setTimeout(() => ring.remove(), 1000);
  }

  function onPhonePreviewPointerMove(event) {
    const start = state.phonePointerStart;
    if (!start || !state.phoneCropMode) return;
    const end = phonePreviewPoint(event);
    const preview = byId("phoneRecorderPreview").getBoundingClientRect();
    const left = Math.min(start.x, end.x) * start.rect.width + (start.rect.left - preview.left);
    const top = Math.min(start.y, end.y) * start.rect.height + (start.rect.top - preview.top);
    const width = Math.abs(end.x - start.x) * start.rect.width;
    const height = Math.abs(end.y - start.y) * start.rect.height;
    Object.assign(els.phoneRecorderCropRect.style, { left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px` });
    els.phoneRecorderCropRect.hidden = false;
  }

  function onPhonePreviewPointerDown(event) {
    const recording = state.phoneRecording;
    if (!state.phoneCropMode && recording?.status !== "recording") return;
    event.preventDefault();
    const point = phonePreviewPoint(event);
    if (!point.inside) return;
    if (!state.phoneCropMode) showPhoneTouchRing(event.clientX, event.clientY);
    state.phonePointerStart = { x: point.x, y: point.y, clientX: event.clientX, clientY: event.clientY, startedAt: performance.now(), pointerId: event.pointerId, rect: point.rect, parent: point.parent };
    els.phoneRecorderImage.setPointerCapture?.(event.pointerId);
  }

  async function onPhonePreviewPointerUp(event) {
    const start = state.phonePointerStart; state.phonePointerStart = null;
    if (!start) return;
    const end = phonePreviewPoint(event);
    if (!end.inside) { els.phoneRecorderCropRect.hidden = true; return; }
    if (state.phoneCropMode) {
      const left = Math.min(start.x, end.x), top = Math.min(start.y, end.y), right = Math.max(start.x, end.x), bottom = Math.max(start.y, end.y);
      if (right - left < 0.025 || bottom - top < 0.025) { toast("Chọn vùng ảnh lớn hơn và có chi tiết dễ nhận biết.", true); return; }
      const source = state.phoneCropFrame || state.phoneFrame;
      const frameId = source?.frame_id || source?.id;
      const crop = await api(`/automation/phone/recordings/${encodeURIComponent(state.phoneRecording.id)}/crop`, {
        method: "POST", body: JSON.stringify({ frame_id: frameId, event_index: state.phoneCropEventIndex || null,
          name: `Phone target ${state.phoneAssets.length + 1}`, box: { x: left, y: top, right, bottom } }),
      });
      if (crop.event) state.phoneRecording.events = (state.phoneRecording.events || []).map((item) => Number(item.index) === Number(crop.event.index) ? crop.event : item);
      await loadPhoneAssets(); renderPhoneRecorderEvents();
      state.phoneCropMode = false; byId("phoneRecorderCropBtn").textContent = "Cắt ảnh mẫu"; els.phoneRecorderCropRect.hidden = true;
      state.phoneCropEventIndex = null; state.phoneCropFrame = null;
      state.phoneMatchPreview = null; els.phoneRecorderMatchRect.hidden = true;
      if (state.phoneFrame) displayPhoneRecorderFrame(state.phoneFrame);
      startPhoneFrameStreaming();
      toast("Đã lưu ảnh mẫu từ ảnh gốc của phone."); return;
    }
    const source = state.phoneFrame;
    if (!source) return;
    const x1 = Math.round(start.x * source.width), y1 = Math.round(start.y * source.height);
    const x2 = Math.round(end.x * source.width), y2 = Math.round(end.y * source.height);
    const movedPx = Math.hypot(event.clientX - start.clientX, event.clientY - start.clientY);
    const heldMs = performance.now() - start.startedAt;
    if (movedPx >= 8) {
      await recordPhoneAction({ type: "swipe", x1, y1, x2, y2, duration_ms: 450 });
    } else if (heldMs >= 650) {
      await recordPhoneAction({ type: "long_press", x: x1, y: y1, duration_ms: Math.min(5000, Math.round(heldMs)) });
    } else {
      await recordPhoneAction({ type: "tap", x: x1, y: y1 });
    }
  }

  function defaultExtensionsConfig() {
    return {
      load_extensions: true,
      disable_extension_welcome_page: true,
      disable_other_extensions: false,
      startup_args: [],
      items: [],
    };
  }

  function normalizeExtensionsConfig(payload) {
    const base = defaultExtensionsConfig();
    const raw = payload && typeof payload === "object" ? payload : {};
    const startupArgs = Array.isArray(raw.startup_args)
      ? raw.startup_args
          .map((arg) => String(arg || "").trim())
          .filter(Boolean)
      : [];
    const items = Array.isArray(raw.items)
      ? raw.items
          .filter((item) => item && typeof item === "object")
          .map((item, idx) => ({
            id: String(item.id || uniqueId(`ext_${idx}`)),
            name: String(item.name || `Extension ${idx + 1}`),
            source_type: String(item.source_type || "path"),
            path: String(item.path || ""),
            url: String(item.url || ""),
            version: String(item.version || ""),
            manifest_version: String(item.manifest_version || ""),
            enabled: item.enabled !== false,
            created_at: Number(item.created_at || Date.now() / 1000),
            note: String(item.note || ""),
            runtime_status: String(item.runtime_status || "ready"),
            status_note: String(item.status_note || ""),
          }))
      : [];
    return {
      load_extensions: raw.load_extensions !== false,
      disable_extension_welcome_page: raw.disable_extension_welcome_page !== false,
      disable_other_extensions: raw.disable_other_extensions === true,
      startup_args: startupArgs,
      items,
    };
  }

  function setExtensionsControlsDisabled(disabled) {
    const controls = [
      els.refreshExtensionsBtn,
      els.uploadExtensionBtn,
      els.importUrlExtensionBtn,
      els.extensionFileInput,
      els.extLoadEnabled,
      els.extDisableWelcome,
      els.extDisableOther,
      els.extensionPathInput,
      els.addPathExtensionBtn,
      els.extensionStartupArgs,
    ];
    controls.forEach((el) => {
      if (!el) return;
      el.disabled = !!disabled;
    });
    els.extensionList.querySelectorAll("button, input").forEach((el) => {
      el.disabled = !!disabled;
    });
  }

  function cloneJson(value) {
    return JSON.parse(JSON.stringify(value));
  }

  async function loadExtensionConfig() {
    const data = await api("/automation/extensions/config");
    state.extensionsConfig = normalizeExtensionsConfig(data);
    renderExtensionsSection();
  }

  async function persistExtensionConfig(nextConfig, successMessage) {
    const payload = normalizeExtensionsConfig(nextConfig);
    state.extensionsSaving = true;
    setExtensionsControlsDisabled(true);
    try {
      const saved = await api("/automation/extensions/config", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      state.extensionsConfig = normalizeExtensionsConfig(saved);
      renderExtensionsSection();
      if (successMessage) toast(successMessage);
    } finally {
      state.extensionsSaving = false;
      setExtensionsControlsDisabled(false);
    }
  }

  function renderExtensionsSection() {
    const config = normalizeExtensionsConfig(state.extensionsConfig);
    state.extensionsConfig = config;
    els.extLoadEnabled.checked = !!config.load_extensions;
    els.extDisableWelcome.checked = !!config.disable_extension_welcome_page;
    els.extDisableOther.checked = !!config.disable_other_extensions;
    els.extensionStartupArgs.value = config.startup_args.join("\n");

    els.extensionList.innerHTML = "";
    if (!config.items.length) {
      els.extensionList.innerHTML = "<div class='extension-empty'>No extension configured.</div>";
      return;
    }

    config.items.forEach((item) => {
      const card = document.createElement("div");
      const runtime = String(item.runtime_status || "ready");
      card.className = "extension-card" + (runtime !== "ready" ? " warning" : "");
      const versionText =
        item.version || item.manifest_version
          ? `v${escapeHtml(item.version || "?")} | mv${escapeHtml(item.manifest_version || "?")}`
          : "No version info";
      const sourceText =
        item.source_type === "url"
          ? escapeHtml(item.url || "(URL metadata)")
          : escapeHtml(item.path || "(missing path)");
      const runtimeText = runtime === "ready" ? "Ready" : escapeHtml(item.status_note || runtime);
      card.innerHTML = `
        <div class="extension-card-top">
          <div>
            <div class="extension-name">${escapeHtml(item.name)}</div>
            <div class="extension-version">${versionText}</div>
          </div>
          <label class="extension-toggle">
            <input type="checkbox" ${item.enabled ? "checked" : ""} data-ext-toggle="${escapeHtml(item.id)}" />
            <span>${item.enabled ? "ON" : "OFF"}</span>
          </label>
        </div>
        <div class="extension-source">${sourceText}</div>
        <div class="extension-runtime">${runtimeText}</div>
        <div class="extension-card-actions">
          <button class="ghost extension-copy-path-btn" data-ext-copy="${escapeHtml(item.id)}">Copy Path</button>
          <button class="danger extension-remove-btn" data-ext-remove="${escapeHtml(item.id)}">Remove</button>
        </div>
      `;
      els.extensionList.appendChild(card);
    });

    els.extensionList.querySelectorAll("[data-ext-toggle]").forEach((input) => {
      input.addEventListener("change", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) return;
        const id = String(target.dataset.extToggle || "");
        toggleExtensionItem(id, target.checked).catch((err) => {
          toast("Toggle extension failed: " + err.message, true);
        });
      });
    });

    els.extensionList.querySelectorAll("[data-ext-remove]").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        const target = event.currentTarget;
        if (!(target instanceof HTMLElement)) return;
        const id = String(target.dataset.extRemove || "");
        removeExtensionItem(id).catch((err) => {
          toast("Remove extension failed: " + err.message, true);
        });
      });
    });

    els.extensionList.querySelectorAll("[data-ext-copy]").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        const target = event.currentTarget;
        if (!(target instanceof HTMLElement)) return;
        const id = String(target.dataset.extCopy || "");
        const ext = config.items.find((item) => item.id === id);
        if (!ext || !ext.path) {
          toast("No local path to copy", true);
          return;
        }
        navigator.clipboard
          .writeText(ext.path)
          .then(() => toast("Path copied"))
          .catch(() => toast("Copy path failed", true));
      });
    });
  }

  function updateExtensionFlag(key, value) {
    const config = normalizeExtensionsConfig(state.extensionsConfig);
    config[key] = !!value;
    persistExtensionConfig(config, "Extension setting updated").catch((err) => {
      toast("Update extension setting failed: " + err.message, true);
    });
  }

  async function saveStartupArgs() {
    const config = normalizeExtensionsConfig(state.extensionsConfig);
    config.startup_args = String(els.extensionStartupArgs.value || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    await persistExtensionConfig(config, "Startup args saved");
  }

  async function addPathExtension() {
    const path = String(els.extensionPathInput.value || "").trim();
    if (!path) {
      toast("Path is required", true);
      return;
    }
    const config = normalizeExtensionsConfig(state.extensionsConfig);
    config.items.unshift({
      id: uniqueId("ext"),
      name: PathName(path),
      source_type: "path",
      path,
      url: "",
      version: "",
      manifest_version: "",
      enabled: true,
      created_at: Date.now() / 1000,
      note: "",
      runtime_status: "ready",
      status_note: "",
    });
    els.extensionPathInput.value = "";
    await persistExtensionConfig(config, "Path extension added");
  }

  function PathName(path) {
    const clean = String(path || "").replace(/\\/g, "/");
    const parts = clean.split("/").filter(Boolean);
    return parts.length ? parts[parts.length - 1] : "Extension";
  }

  async function handleExtensionUpload() {
    const files = Array.from(els.extensionFileInput.files || []);
    if (!files.length) return;
    const file = files[0];
    const body = new FormData();
    body.append("file", file, file.name);
    state.extensionsSaving = true;
    setExtensionsControlsDisabled(true);
    try {
      const saved = await api("/automation/extensions/upload", {
        method: "POST",
        body,
      });
      state.extensionsConfig = normalizeExtensionsConfig(saved);
      renderExtensionsSection();
      toast(`Uploaded extension: ${file.name}`);
    } finally {
      els.extensionFileInput.value = "";
      state.extensionsSaving = false;
      setExtensionsControlsDisabled(false);
    }
  }

  async function importExtensionFromUrl() {
    const url = prompt("Paste direct .zip extension URL");
    if (!url) return;
    state.extensionsSaving = true;
    setExtensionsControlsDisabled(true);
    try {
      const saved = await api("/automation/extensions/import-url", {
        method: "POST",
        body: JSON.stringify({ url: String(url).trim() }),
      });
      state.extensionsConfig = normalizeExtensionsConfig(saved);
      renderExtensionsSection();
      toast("Extension imported from URL");
    } finally {
      state.extensionsSaving = false;
      setExtensionsControlsDisabled(false);
    }
  }

  async function toggleExtensionItem(id, enabled) {
    const config = cloneJson(normalizeExtensionsConfig(state.extensionsConfig));
    const item = config.items.find((entry) => entry.id === id);
    if (!item) return;
    item.enabled = !!enabled;
    await persistExtensionConfig(config, "Extension updated");
  }

  async function removeExtensionItem(id) {
    const config = cloneJson(normalizeExtensionsConfig(state.extensionsConfig));
    const before = config.items.length;
    config.items = config.items.filter((entry) => entry.id !== id);
    if (config.items.length === before) return;
    await persistExtensionConfig(config, "Extension removed");
  }

  async function loadCatalog() {
    const data = await api("/automation/catalog");
    state.catalog = data.categories || [];
    state.defaultsByType = {};
    state.catalog.forEach((group) => {
      (group.nodes || []).forEach((nodeDef) => {
        state.defaultsByType[nodeDef.type] = JSON.parse(
          JSON.stringify(nodeDef.default_config || {})
        );
      });
    });
    renderPalette();
  }

  function renderPalette() {
    els.palette.replaceChildren();
    const header = document.createElement("div");
    header.className = "palette-header";
    header.innerHTML = '<h3>Thêm node</h3><span class="palette-count"></span>';
    const search = document.createElement("input");
    search.type = "search";
    search.id = "paletteSearch";
    search.className = "palette-search";
    search.placeholder = "Tìm node...";
    search.setAttribute("aria-label", "Tìm node theo tên");
    els.palette.append(header, search);

    const groups = [];
    state.catalog.forEach((group, groupIndex) => {
      const section = document.createElement("details");
      section.className = "palette-group";
      section.open = groupIndex === 0;
      const summary = document.createElement("summary");
      const items = group.nodes || [];
      summary.innerHTML = `<span>${escapeHtml(paletteGroupLabel(group.label))}</span><small>${items.length}</small>`;
      section.appendChild(summary);
      const list = document.createElement("div");
      list.className = "palette-group-items";
      items.forEach((nodeDef) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "palette-node";
        card.draggable = true;
        card.dataset.search = `${nodeLabelEn(nodeDef.type)} ${nodeDef.type}`.toLowerCase();
        card.innerHTML = `<span class="palette-node-icon" aria-hidden="true">${escapeHtml(nodeIcon(nodeDef.type))}</span><strong>${escapeHtml(nodeLabelEn(nodeDef.type))}</strong>`;
        card.addEventListener("dragstart", (event) => {
          event.dataTransfer.setData("application/x-node", JSON.stringify(nodeDef));
        });
        card.addEventListener("click", () => {
          const canvasRect = els.canvas.getBoundingClientRect();
          const worldRect = els.canvasWorld.getBoundingClientRect();
          const x = Math.max(24, (canvasRect.left + els.canvas.clientWidth / 2 - worldRect.left) / state.canvasZoom - 95);
          const y = Math.max(24, (canvasRect.top + els.canvas.clientHeight / 2 - worldRect.top) / state.canvasZoom - 29);
          addNode(nodeDef.type, nodeDef.default_config || {}, x, y);
          renderCanvas();
        });
        list.appendChild(card);
      });
      section.appendChild(list);
      els.palette.appendChild(section);
      groups.push({ section, items: Array.from(list.querySelectorAll(".palette-node")) });
    });

    const total = groups.reduce((count, group) => count + group.items.length, 0);
    header.querySelector(".palette-count").textContent = `${total} node`;
    search.addEventListener("input", () => {
      const query = search.value.trim().toLowerCase();
      groups.forEach(({ section, items }) => {
        let visibleCount = 0;
        items.forEach((item) => {
          const matches = !query || item.dataset.search.includes(query);
          item.hidden = !matches;
          if (matches) visibleCount += 1;
        });
        section.hidden = visibleCount === 0;
        if (query && visibleCount) section.open = true;
        if (!query) section.open = section === groups[0]?.section;
      });
    });
  }

  function newGraph() {
    state.currentAppId = null;
    seedDefaultGraph();
    state.inputs = [];
    state.inspectorTabByNodeId = {};
    state.connectDraft.active = false;
    els.appName.value = "";
    els.appDesc.value = "";
    els.appVersion.textContent = "Bản nháp";
    els.taskName.value = "";
    els.nodeConfigEditor.value = "";
    els.newConfigKey.value = "";
    els.newConfigValue.value = "";
    renderCanvas();
    renderNodeInspector();
    renderEdgeList();
    renderAppList();
    renderAppRunInputs();
  }

  function clearCanvas() {
    state.nodes = [];
    state.edges = [];
    state.selectedNodeId = null;
    state.inspectorTabByNodeId = {};
    state.connectDraft.active = false;
    renderCanvas();
    renderNodeInspector();
    renderEdgeList();
    renderAppTabs();
  }

  function startNewApp() {
    newGraph();
    setAppEditorView("editor");
    els.appName.focus();
  }

  function goToAppHome() {
    setAppEditorView("home");
  }

  function requestAppHome() {
    const prompt = byId("saveAppPrompt");
    if (!prompt.open) prompt.showModal();
  }

  function returnToAppHome() {
    setWorkspacePanel(false);
    setAppEditorView("home");
  }

  function setAppEditorView(view) {
    state.appEditorView = view === "editor" ? "editor" : "home";
    els.appHome.classList.toggle("is-hidden", state.appEditorView !== "home");
    els.builderLayout.classList.toggle("is-hidden", state.appEditorView !== "editor");
    if (state.appEditorView === "home") {
      stopExternalRunDiscovery();
      renderAppHome();
    } else {
      syncExternalRunDiscovery();
      loadProfilesForPicker({ silent: true }).catch((err) =>
        toast("Auto profile load failed: " + err.message, true)
      );
    }
    renderAppTabs();
  }

  function seedDefaultGraph() {
    const startId = uniqueId("n");
    const variablesId = uniqueId("n");
    const startConfig = JSON.parse(
      JSON.stringify(state.defaultsByType["Start"] || {})
    );
    const variablesConfig = JSON.parse(
      JSON.stringify(
        state.defaultsByType["Variables"] || {
          custom_variables: [],
          timeout: 30,
        }
      )
    );
    state.nodes = [
      {
        id: startId,
        type: "Start",
        config: startConfig,
        x: 120,
        y: 150,
      },
      {
        id: variablesId,
        type: "Variables",
        config: variablesConfig,
        x: 290,
        y: 150,
      },
    ];
    state.edges = [];
    state.selectedNodeId = variablesId;
  }

  function onDropNode(e) {
    e.preventDefault();
    const raw = e.dataTransfer.getData("application/x-node");
    if (!raw) return;
    const payload = JSON.parse(raw);
    const pos = mouseToCanvas(e.clientX, e.clientY);
    addNode(payload.type, payload.default_config || {}, pos.x - 95, pos.y - 20);
    renderCanvas();
  }

  function addNode(type, config, x, y) {
    const id = uniqueId("n");
    state.nodes.push({
      id,
      type,
      config: JSON.parse(JSON.stringify(config || {})),
      x: Math.max(8, Math.round(x)),
      y: Math.max(8, Math.round(y)),
    });
    state.selectedNodeId = id;
    renderNodeInspector();
  }

  function renderCanvas() {
    els.canvas.querySelectorAll(".node").forEach((el) => el.remove());
    els.edgeLayer.innerHTML = "";
    updateCanvasBounds();
    const canvasStepNumbers = buildCanvasNodeStepNumbers();

    state.nodes.forEach((node) => {
      const visual = nodeVisualMeta(node.type);
      const runtimeStep = state.runNodeStepIndices.get(node.id);
      const canvasStep = runtimeStep ?? canvasStepNumbers.get(node.id) ?? null;
      const noteText = String(node?.config?.__note || "").trim();
      const div = document.createElement("div");
      div.className =
        "node " +
        visual.className +
        (state.runningSingleNodeId === node.id ? " running-single" : "") +
        (state.runActiveNodeId === node.id ? " run-active" : "") +
        (state.runFailedNodeIds.has(node.id) ? " run-error" : "") +
        (state.selectedNodeId === node.id ? " active" : "");
      div.dataset.nodeId = node.id;
      div.tabIndex = 0;
      div.setAttribute("role", "group");
      const stepLabel = canvasStep == null ? "" : `. Step ${canvasStep}`;
      const runStateLabel = state.runFailedNodeIds.has(node.id)
        ? ". Lỗi khi chạy node"
        : state.runActiveNodeId === node.id
          ? ". Đang chạy node"
          : "";
      div.setAttribute("aria-label", `${visual.label}${stepLabel}${runStateLabel}. Nhấp đúp để mở thuộc tính`);
      div.style.left = `${node.x}px`;
      div.style.top = `${node.y}px`;
      div.style.width = `${visual.width}px`;
      if (visual.height) {
        div.style.height = `${visual.height}px`;
      } else {
        div.style.height = "";
      }
      div.innerHTML = `
        <div class="node-tools">
          <button class="node-tool node-tool-delete" title="Xóa node" aria-label="Xóa node">🗑</button>
          <button class="node-tool node-tool-run" title="Chạy từ node này theo các kết nối tiếp theo" aria-label="Chạy từ node này theo các kết nối tiếp theo">▶</button>
        </div>
        ${canvasStep == null ? "" : `
          <span class="node-step-badge${runtimeStep == null ? "" : " is-runtime"}"
            data-static-step="${canvasStepNumbers.get(node.id) ?? canvasStep}"
            title="${runtimeStep == null ? "Vị trí trong sơ đồ" : "Step của lần chạy gần nhất"}">${canvasStep}</span>
        `}
        ${noteText ? `
          <div class="node-note-indicator" title="Ghi chú node">
            📝
            <div class="node-note-tooltip">${escapeHtml(noteText)}</div>
          </div>
        ` : ""}
        <div class="node-head">
          <span class="node-icon" aria-hidden="true">${escapeHtml(visual.icon)}</span>
          <span class="node-type">${escapeHtml(visual.label)}</span>
        </div>
        <span class="port in" title="Input"></span>
        <span class="port out out-true" data-edge-label="true" title="True / Success"></span>
        <span class="port out out-false" data-edge-label="false" title="False / Error"></span>
      `;

      div.addEventListener("click", (e) => {
        const target = e.target;
        if (!(target instanceof HTMLElement)) return;
        if (target.closest(".port, .node-tool")) {
          return;
        }
        state.selectedNodeId = node.id;
        els.canvas.querySelectorAll(".node.active").forEach((activeNode) => activeNode.classList.remove("active"));
        div.classList.add("active");
      });

      div.addEventListener("dblclick", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement) || target.closest(".port, .node-tool")) return;
        event.preventDefault();
        openNodeProperties(node.id);
      });

      div.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openNodeProperties(node.id);
      });

      const head = div.querySelector(".node-head");
      head.addEventListener("mousedown", (e) => {
        if (e.target.classList.contains("port")) return;
        state.dragNodeId = node.id;
        const pos = mouseToCanvas(e.clientX, e.clientY);
        state.dragOffset = { x: pos.x - node.x, y: pos.y - node.y };
      });

      div.querySelectorAll(".port.out").forEach((outPort) => {
        outPort.addEventListener("mousedown", (e) => {
          e.stopPropagation();
          const target = e.currentTarget;
          const label =
            target instanceof HTMLElement
              ? String(target.dataset.edgeLabel || "next").toLowerCase()
              : "next";
          const pos = mouseToCanvas(e.clientX, e.clientY);
          startConnectWire(node.id, label, pos.x, pos.y);
        });
      });

      const inPort = div.querySelector(".port.in");
      inPort.addEventListener("mouseup", (e) => {
        e.stopPropagation();
        if (!state.connectDraft.active || !state.connectDraft.fromNodeId) return;
        if (state.connectDraft.fromNodeId === node.id) {
          cancelConnectWire();
          return;
        }
        createOrReplaceEdge(
          state.connectDraft.fromNodeId,
          node.id,
          state.connectDraft.fromLabel || "next"
        );
        cancelConnectWire();
        renderEdgeList();
        renderCanvas();
      });

      const deleteBtn = div.querySelector(".node-tool-delete");
      deleteBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        removeNodeById(node.id);
      });

      const runBtn = div.querySelector(".node-tool-run");
      runBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        runSingleNode(node.id).catch((err) => toast("Run node failed: " + err.message, true));
      });

      els.canvasWorld.appendChild(div);
    });

    drawEdges();
  }

  function isStepIndexExcludedNodeType(nodeType) {
    const normalized = normaliseNodeType(nodeType);
    return normalized === "start" || normalized === "start_stop" || normalized === "variables" || normalized === "variable";
  }

  function buildCanvasNodeStepNumbers() {
    const nodesById = new Map(state.nodes.map((node) => [String(node.id), node]));
    const outgoing = new Map();
    state.edges.forEach((edge) => {
      const from = String(edge.from || "");
      if (!outgoing.has(from)) outgoing.set(from, []);
      outgoing.get(from).push(String(edge.to || ""));
    });

    const visited = new Set();
    const ordered = [];
    const visit = (nodeId) => {
      const id = String(nodeId || "");
      if (!id || visited.has(id) || !nodesById.has(id)) return;
      visited.add(id);
      const node = nodesById.get(id);
      if (!isStepIndexExcludedNodeType(node.type)) ordered.push(id);
      (outgoing.get(id) || []).forEach(visit);
    };

    const startNode = state.nodes.find((node) => isStepIndexExcludedNodeType(node.type) && normaliseNodeType(node.type) !== "variables" && normaliseNodeType(node.type) !== "variable");
    if (startNode) visit(startNode.id);
    state.nodes.forEach((node) => visit(node.id));
    return new Map(ordered.map((nodeId, index) => [nodeId, index + 1]));
  }

  function updateNodeStepBadge(nodeId) {
    const id = String(nodeId || "");
    const element = els.canvas.querySelector(`[data-node-id="${CSS.escape(id)}"]`);
    if (!element) return;
    const badge = element.querySelector(".node-step-badge");
    const node = state.nodes.find((candidate) => String(candidate.id) === id);
    const staticStep = Number(badge?.dataset.staticStep || 0);
    const runtimeStep = state.runNodeStepIndices.get(id);
    const displayStep = runtimeStep ?? (staticStep || null);
    if (badge) {
      if (displayStep == null) {
        badge.remove();
      } else {
        badge.textContent = String(displayStep);
        badge.classList.toggle("is-runtime", runtimeStep != null);
        badge.title = runtimeStep == null ? "Vị trí trong sơ đồ" : "Step của lần chạy gần nhất";
      }
    }
    if (node) {
      const elementLabel = nodeVisualMeta(node.type).label;
      const runStateLabel = state.runFailedNodeIds.has(id)
        ? ". Lỗi khi chạy node"
        : state.runActiveNodeId === id
          ? ". Đang chạy node"
          : "";
      const stepLabel = displayStep == null ? "" : `. Step ${displayStep}`;
      element.setAttribute("aria-label", `${elementLabel}${stepLabel}${runStateLabel}. Nhấp đúp để mở thuộc tính`);
    }
  }

  function startConnectWire(fromNodeId, fromLabel, mouseX, mouseY) {
    state.connectDraft.active = true;
    state.connectDraft.fromNodeId = fromNodeId;
    state.connectDraft.fromLabel = fromLabel || "next";
    state.connectDraft.mouseX = mouseX;
    state.connectDraft.mouseY = mouseY;
    drawEdges();
  }

  function cancelConnectWire() {
    state.connectDraft.active = false;
    state.connectDraft.fromNodeId = null;
    state.connectDraft.fromLabel = "next";
  }

  function onCanvasMouseMove(e) {
    if (!state.connectDraft.active) return;
    const pos = mouseToCanvas(e.clientX, e.clientY);
    state.connectDraft.mouseX = pos.x;
    state.connectDraft.mouseY = pos.y;
    drawEdges();
  }

  function onCanvasMouseDown(event) {
    if (event.button !== 0 || state.connectDraft.active) return;
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.closest(".node, .canvas-zoom-controls")) return;

    state.canvasPan = {
      startX: event.clientX,
      startY: event.clientY,
      scrollLeft: els.canvas.scrollLeft,
      scrollTop: els.canvas.scrollTop,
    };
    els.canvas.classList.add("is-panning");
    event.preventDefault();
  }

  function onDragMove(e) {
    if (state.canvasPan) {
      els.canvas.scrollLeft = state.canvasPan.scrollLeft + state.canvasPan.startX - e.clientX;
      els.canvas.scrollTop = state.canvasPan.scrollTop + state.canvasPan.startY - e.clientY;
      return;
    }
    if (!state.dragNodeId) return;
    const node = state.nodes.find((n) => n.id === state.dragNodeId);
    if (!node) return;
    const pos = mouseToCanvas(e.clientX, e.clientY);
    state.pendingDragPosition = {
      nodeId: node.id,
      x: Math.max(0, Math.round(pos.x - state.dragOffset.x)),
      y: Math.max(0, Math.round(pos.y - state.dragOffset.y)),
    };
    if (state.dragFrameId) return;
    state.dragFrameId = window.requestAnimationFrame(() => {
      state.dragFrameId = 0;
      const pending = state.pendingDragPosition;
      state.pendingDragPosition = null;
      if (!pending) return;
      const movingNode = state.nodes.find((entry) => entry.id === pending.nodeId);
      const nodeElement = els.canvas.querySelector(`[data-node-id="${CSS.escape(pending.nodeId)}"]`);
      if (!movingNode || !nodeElement) return;
      movingNode.x = pending.x;
      movingNode.y = pending.y;
      nodeElement.style.left = `${pending.x}px`;
      nodeElement.style.top = `${pending.y}px`;
      updateCanvasBounds();
      drawEdges();
    });
  }

  function onWindowMouseUp() {
    state.dragNodeId = null;
    state.canvasPan = null;
    els.canvas.classList.remove("is-panning");
    if (state.connectDraft.active) {
      cancelConnectWire();
      drawEdges();
    }
  }

  function mouseToCanvas(clientX, clientY) {
    const worldRect = els.canvasWorld.getBoundingClientRect();
    return {
      x: (clientX - worldRect.left) / state.canvasZoom,
      y: (clientY - worldRect.top) / state.canvasZoom,
    };
  }

  function setCanvasZoom(nextZoom, options = {}) {
    const minZoom = 0.25;
    const maxZoom = 2;
    const previousZoom = state.canvasZoom;
    const next = Math.min(maxZoom, Math.max(minZoom, Math.round(nextZoom * 100) / 100));
    if (next === previousZoom) return;

    const centerX = (els.canvas.scrollLeft + els.canvas.clientWidth / 2) / previousZoom;
    const centerY = (els.canvas.scrollTop + els.canvas.clientHeight / 2) / previousZoom;
    state.canvasZoom = next;
    els.canvasWorld.style.zoom = String(next);
    els.canvas.style.backgroundSize = `${Math.max(10, 20 * next)}px ${Math.max(10, 20 * next)}px`;
    els.canvasZoomLabel.textContent = `${Math.round(next * 100)}%`;
    els.canvasZoomOutBtn.disabled = next <= minZoom;
    els.canvasZoomInBtn.disabled = next >= maxZoom;
    updateCanvasBounds();
    drawEdges();

    if (options.preserveCenter !== false) {
      els.canvas.scrollLeft = Math.max(0, centerX * next - els.canvas.clientWidth / 2);
      els.canvas.scrollTop = Math.max(0, centerY * next - els.canvas.clientHeight / 2);
    }
  }

  function fitCanvasToNodes() {
    if (!state.nodes.length) {
      setCanvasZoom(1, { preserveCenter: false });
      els.canvas.scrollLeft = 0;
      els.canvas.scrollTop = 0;
      return;
    }

    const bounds = state.nodes.reduce((acc, node) => {
      const visual = nodeVisualMeta(node.type);
      acc.left = Math.min(acc.left, node.x);
      acc.top = Math.min(acc.top, node.y);
      acc.right = Math.max(acc.right, node.x + visual.width);
      acc.bottom = Math.max(acc.bottom, node.y + (visual.height || 58));
      return acc;
    }, { left: Infinity, top: Infinity, right: 0, bottom: 0 });
    const padding = 56;
    const contentWidth = Math.max(1, bounds.right - bounds.left);
    const contentHeight = Math.max(1, bounds.bottom - bounds.top);
    const fitZoom = Math.min(
      1,
      (els.canvas.clientWidth - padding * 2) / contentWidth,
      (els.canvas.clientHeight - padding * 2) / contentHeight
    );
    setCanvasZoom(fitZoom, { preserveCenter: false });
    els.canvas.scrollLeft = Math.max(0, bounds.left * state.canvasZoom - padding);
    els.canvas.scrollTop = Math.max(0, bounds.top * state.canvasZoom - padding);
  }

  function getNodeAnchor(node, side, edgeLabel = "next") {
    const visual = nodeVisualMeta(node.type);
    const centerY = node.y + (visual.height || 40) / 2;
    if (side === "out") {
      const label = String(edgeLabel || "next").toLowerCase();
      const offset = label === "false" || label === "error" ? 8 : -8;
      return { x: node.x + visual.width, y: centerY + offset };
    }
    const y = centerY;
    return { x: node.x, y };
  }

  function nodeVisualMeta(nodeType) {
    const normalised = normaliseNodeType(nodeType);
    const raw = String(nodeType || "").trim();
    if (normalised === "start") {
      return { className: "node-start", width: 74, height: 74, label: nodeLabelEn(raw), icon: nodeIcon(raw) };
    }
    if (normalised === "stop") {
      return { className: "node-stop", width: 178, height: 58, label: nodeLabelEn(raw), icon: nodeIcon(raw) };
    }
    if (raw.toLowerCase().includes("variable")) {
      return { className: "node-variable", width: 178, height: 58, label: nodeLabelEn(raw), icon: nodeIcon(raw) };
    }
    if (raw.toLowerCase().includes("context")) {
      return { className: "node-context", width: 178, height: 58, label: nodeLabelEn(raw), icon: nodeIcon(raw) };
    }
    return { className: "node-action", width: 190, height: 58, label: nodeLabelEn(raw), icon: nodeIcon(raw) };
  }

  function updateCanvasBounds() {
    const workspacePadding = 480;
    const width = Math.max(
      els.canvas.clientWidth / state.canvasZoom + workspacePadding,
      ...state.nodes.map((node) => node.x + nodeVisualMeta(node.type).width + workspacePadding),
      480
    );
    const height = Math.max(
      els.canvas.clientHeight / state.canvasZoom + workspacePadding,
      ...state.nodes.map((node) => node.y + (nodeVisualMeta(node.type).height || 58) + workspacePadding),
      320
    );
    els.canvasWorld.style.width = `${width}px`;
    els.canvasWorld.style.height = `${height}px`;
    els.edgeLayer.setAttribute("width", String(width));
    els.edgeLayer.setAttribute("height", String(height));
    els.edgeLayer.setAttribute("viewBox", `0 0 ${width} ${height}`);
  }

  function drawEdges() {
    const ns = "http://www.w3.org/2000/svg";
    els.edgeLayer.innerHTML = "";

    state.edges.forEach((edge, edgeIndex) => {
      const from = state.nodes.find((n) => n.id === edge.from);
      const to = state.nodes.find((n) => n.id === edge.to);
      if (!from || !to) return;
      const label = String(edge.label || "next").toLowerCase();
      const p1 = getNodeAnchor(from, "out", label);
      const p2 = getNodeAnchor(to, "in");
      drawBezier(ns, p1.x, p1.y, p2.x, p2.y, edgeColorForLabel(label), edgeIndex, edge);
    });

    if (state.connectDraft.active && state.connectDraft.fromNodeId) {
      const from = state.nodes.find((n) => n.id === state.connectDraft.fromNodeId);
      if (from) {
        const draftLabel = String(state.connectDraft.fromLabel || "next").toLowerCase();
        const p1 = getNodeAnchor(from, "out", draftLabel);
        drawBezier(
          ns,
          p1.x,
          p1.y,
          state.connectDraft.mouseX,
          state.connectDraft.mouseY,
          edgeColorForLabel(draftLabel)
        );
      }
    }
  }

  function edgeColorForLabel(label) {
    const key = String(label || "next").toLowerCase();
    if (key === "true" || key === "success" || key === "next") return "#63d9a0";
    if (key === "false" || key === "error" || key === "fallback") return "#ff5f78";
    if (key === "loop" || key === "break") return "#8fc2ff";
    return "#7ea0d4";
  }

  function drawBezier(ns, x1, y1, x2, y2, color, edgeIndex = null, edge = null) {
    const cdx = Math.max(40, Math.abs(x2 - x1) * 0.35);
    const cx1 = x1 + cdx;
    const cx2 = x2 - cdx;
    const pathData = `M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`;

    if (edgeIndex !== null) {
      const group = document.createElementNS(ns, "g");
      group.classList.add("edge-connection");

      const hitArea = document.createElementNS(ns, "path");
      hitArea.setAttribute("d", pathData);
      hitArea.setAttribute("class", "edge-hit-area");
      group.appendChild(hitArea);

      const visiblePath = document.createElementNS(ns, "path");
      visiblePath.setAttribute("d", pathData);
      visiblePath.setAttribute("fill", "none");
      visiblePath.setAttribute("stroke", color);
      visiblePath.setAttribute("stroke-width", "2");
      visiblePath.setAttribute("class", "edge-visible-path");
      group.appendChild(visiblePath);

      const removeButton = document.createElementNS(ns, "g");
      const midpointX = (x1 + x2) / 2;
      const midpointY = (y1 + y2) / 2;
      removeButton.setAttribute("class", "edge-delete-control");
      removeButton.setAttribute("transform", `translate(${midpointX} ${midpointY})`);
      removeButton.setAttribute("role", "button");
      removeButton.setAttribute("tabindex", "0");
      removeButton.setAttribute(
        "aria-label",
        `Xóa kết nối ${String(edge?.from || "")} đến ${String(edge?.to || "")}`
      );

      const title = document.createElementNS(ns, "title");
      title.textContent = `Xóa kết nối ${String(edge?.from || "")} → ${String(edge?.to || "")}`;
      removeButton.appendChild(title);

      const buttonBackground = document.createElementNS(ns, "circle");
      buttonBackground.setAttribute("class", "edge-delete-background");
      buttonBackground.setAttribute("r", "11");
      removeButton.appendChild(buttonBackground);

      const cross = document.createElementNS(ns, "path");
      cross.setAttribute("class", "edge-delete-cross");
      cross.setAttribute("d", "M -3.5 -3.5 L 3.5 3.5 M 3.5 -3.5 L -3.5 3.5");
      removeButton.appendChild(cross);

      const removeEdge = (event) => {
        event.preventDefault();
        event.stopPropagation();
        removeEdgeAt(edgeIndex);
      };
      removeButton.addEventListener("mousedown", (event) => {
        event.preventDefault();
        event.stopPropagation();
      });
      removeButton.addEventListener("click", removeEdge);
      removeButton.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        removeEdge(event);
      });
      group.appendChild(removeButton);
      els.edgeLayer.appendChild(group);
      return;
    }

    const path = document.createElementNS(ns, "path");
    path.setAttribute("d", pathData);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", color);
    path.setAttribute("stroke-width", "2");
    els.edgeLayer.appendChild(path);
  }

  function removeEdgeAt(edgeIndex) {
    if (!Number.isInteger(edgeIndex) || edgeIndex < 0 || edgeIndex >= state.edges.length) return;
    state.edges.splice(edgeIndex, 1);
    renderEdgeList();
    drawEdges();
  }

  function createOrReplaceEdge(fromId, toId, label) {
    const existing = state.edges.find((e) => e.from === fromId && e.label === label);
    if (existing) {
      existing.to = toId;
      return;
    }
    state.edges.push({ from: fromId, to: toId, label: label || "next" });
  }
  function renderNodeInspector() {
    const node = getEditableNode(state.selectedNodeId);
    if (!node) {
      els.nodeMeta.textContent = "Chọn node để chỉnh cấu hình";
      els.nodeForm.innerHTML = "";
      els.nodeConfigEditor.value = "";
      els.nodeDialogTitle.textContent = "Thuộc tính node";
      els.nodeDialogIcon.textContent = "";
      return;
    }
    const visual = nodeVisualMeta(node.type);
    els.nodeDialogTitle.textContent = visual.label;
    els.nodeDialogIcon.textContent = visual.icon;
    els.nodeMeta.textContent = `${nodeLabelEn(node.type)} · ID ${node.id}`;
    renderNodeForm(node);
    els.nodeConfigEditor.value = JSON.stringify(node.config || {}, null, 2);
  }

  function openNodeProperties(nodeId) {
    const node = state.nodes.find((item) => item.id === nodeId);
    if (!node) return;
    state.selectedNodeId = node.id;
    state.openNodePropertiesId = node.id;
    state.nodeDraft = cloneJson(node);
    renderCanvasSelection(node.id);
    renderNodeInspector();
    if (!els.nodePropertiesDialog.open) {
      els.nodePropertiesDialog.showModal();
    }
  }

  function renderCanvasSelection(nodeId) {
    els.canvas.querySelectorAll(".node.active").forEach((activeNode) => {
      activeNode.classList.remove("active");
    });
    const selectedNode = els.canvas.querySelector(`[data-node-id="${CSS.escape(nodeId)}"]`);
    if (selectedNode) {
      selectedNode.classList.add("active");
      selectedNode.focus();
    }
  }

  function closeNodeProperties() {
    if (els.nodePropertiesDialog.open) els.nodePropertiesDialog.close();
  }

  function getEditableNode(nodeId = state.selectedNodeId) {
    const id = String(nodeId || "");
    if (!id) return null;
    if (state.nodeDraft?.id === id) return state.nodeDraft;
    return state.nodes.find((node) => node.id === id) || null;
  }

  function saveNodeProperties() {
    const node = state.nodes.find((item) => item.id === state.selectedNodeId);
    const draft = state.nodeDraft;
    if (!node || !draft || draft.id !== node.id) {
      toast("Không tìm thấy node để lưu", true);
      return;
    }

    const editorValue = String(els.nodeConfigEditor.value || "").trim();
    const draftConfig = JSON.stringify(draft.config || {}, null, 2);
    if (editorValue !== draftConfig) {
      try {
        const parsed = JSON.parse(editorValue || "{}");
        if (!isPlainObject(parsed)) throw new Error("Node config must be a JSON object");
        draft.config = parsed;
      } catch (err) {
        toast("JSON không hợp lệ. Sửa hoặc áp dụng JSON trước khi lưu node.", true);
        els.nodeConfigEditor.focus();
        return;
      }
    }

    node.config = cloneJson(draft.config || {});
    state.nodeDraft = null;
    els.nodePropertiesDialog.close();
    renderCanvas();
    toast("Đã lưu cấu hình node vào sơ đồ. Nhớ lưu ứng dụng để lưu lâu dài.");
  }

  function renderNodeForm(node) {
    ensureCommonExecutionDefaults(node);
    els.nodeForm.innerHTML = "";
    if (renderSpecialNodeForm(node)) {
      appendPhoneNodeTestButton(node);
      return;
    }
    renderGenericNodeForm(node);
    appendPhoneNodeTestButton(node);
  }

  function appendPhoneNodeTestButton(node) {
    if (!normaliseNodeType(node.type).startsWith("artemis")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary";
    button.textContent = "Thử riêng node này";
    button.addEventListener("click", () => {
      const saved = state.nodes.find((item) => item.id === node.id);
      if (!saved || JSON.stringify(saved.config) !== JSON.stringify(node.config)) {
        toast("Lưu thuộc tính node trước khi thử riêng", true);
        return;
      }
      runSingleNode(node.id, true).catch((err) => toast("Thử node lỗi: " + err.message, true));
    });
    els.nodeForm.appendChild(button);
  }

  function renderSpecialNodeForm(node) {
    const type = normaliseNodeType(node.type);
    if (type === "analyze_error" || type === "artemis_analyze_error") {
      renderAnalyzeErrorForm(node);
      return true;
    }
    if (type === "call_app") {
      renderCallAppNodeForm(node);
      return true;
    }
    if (type === "artemis_install_apks") {
      renderInstallApksForm(node);
      return true;
    }
    if (type === "artemis_find_image" || type === "artemis_tap_image") {
      renderGenericNodeForm(node);
      renderPhoneImageAssetField(node, true);
      return true;
    }
    if (["artemis_tap", "artemis_long_press", "artemis_double_tap"].includes(type) && node.config?.image_asset_id !== undefined) {
      renderGenericNodeForm(node);
      renderPhoneImageAssetField(node, false);
      return true;
    }
    if (type === "variables" || type === "variable") {
      ensureVariablesDefaults(node);
      renderVariablesForm(node);
      return true;
    }
    if (type === "open_url") {
      ensureOpenUrlDefaults(node);
      renderOpenUrlForm(node);
      return true;
    }
    if (type === "get_text") {
      ensureGetTextDefaults(node);
      renderGetTextForm(node);
      return true;
    }
    if (type === "get_value") {
      ensureGetValueDefaults(node);
      renderGetValueForm(node);
      return true;
    }
    if (type === "select_dropdown") {
      ensureSelectDropdownDefaults(node);
      renderSelectDropdownForm(node);
      return true;
    }
    if (type === "file_upload") {
      ensureFileUploadDefaults(node);
      renderFileUploadForm(node);
      return true;
    }
    if (type === "click") {
      ensureClickDefaults(node);
      renderClickForm(node);
      return true;
    }
    if (type === "element_exist" || type === "element_exists") {
      ensureElementExistDefaults(node);
      renderElementExistForm(node);
      return true;
    }
    if (type === "type_text") {
      ensureTypeTextDefaults(node);
      renderTypeTextForm(node);
      return true;
    }
    return false;
  }

  function renderAnalyzeErrorForm(node) {
    const config = node.config || (node.config = {});
    if (typeof config.output_variable === "undefined") config.output_variable = "node_error_analysis";
    if (typeof config.include_phone_context === "undefined") config.include_phone_context = false;
    if (typeof config.serial_variable === "undefined") config.serial_variable = "artemis_phone";
    if (typeof config.max_auto_retries === "undefined") config.max_auto_retries = 0;

    const panel = createInspectorPanel(
      "Analyze Error",
      "Nhận lỗi qua cổng error của node trước đó; kết quả nằm trong biến đầu ra."
    );
    appendSleepBeforeNodeField(panel, node, config);
    panel.appendChild(createTextField(node, "Biến đầu ra", "output_variable", config.output_variable));
    panel.appendChild(createBooleanField(
      node,
      "Đọc thêm trạng thái phone",
      "include_phone_context",
      config.include_phone_context,
      "Chỉ bật khi cần đối chiếu selector với cây Accessibility hiện tại. Không ghi nội dung màn hình vào log."
    ));
    panel.appendChild(createTextField(node, "Biến kết nối phone", "serial_variable", config.serial_variable));
    panel.appendChild(createNumberField(
      node,
      "Số lần thử lại an toàn tối đa",
      "max_auto_retries",
      config.max_auto_retries,
      { min: 0, max: 3, step: 1, hint: "Chỉ đề xuất thử lại lỗi tạm thời ở node đọc dữ liệu. Muốn thử lại, nối cổng true về node lỗi; cổng false đi tới Log/recovery/Stop. Click, nhập, cài app và thao tác ghi không được tự lặp." }
    ));
    els.nodeForm.appendChild(panel);
  }

  function renderCallAppNodeForm(node) {
    const config = node.config || (node.config = {});
    const panel = createInspectorPanel("Gọi app con", "Chạy app con bằng cùng profile, browser và phiên ARTEMIS phone.");
    appendSleepBeforeNodeField(panel, node, config);
    const appField = document.createElement("div");
    appField.className = "node-field";
    const appLabel = document.createElement("label");
    appLabel.textContent = "Ứng dụng con";
    const select = document.createElement("select");
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Chọn app đã lưu";
    select.appendChild(empty);
    state.apps.filter((app) => String(app.id) !== String(state.currentAppId)).forEach((app) => {
      const option = document.createElement("option");
      option.value = String(app.id);
      option.textContent = `${app.name} · ${app.id}`;
      option.selected = String(config.app_id || "") === String(app.id);
      select.appendChild(option);
    });
    select.addEventListener("change", () => { config.app_id = select.value; syncInspectorState(); });
    appField.append(appLabel, select);
    panel.appendChild(appField);
    [
      ["input_mapping", "Ánh xạ đầu vào JSON", "Tên biến app con → giá trị hoặc {biến_app_cha}"],
      ["output_mapping", "Ánh xạ đầu ra JSON", "Tên biến app cha → tên biến đầu ra app con"],
    ].forEach(([key, title, hintText]) => {
      const field = document.createElement("div");
      field.className = "node-field";
      const label = document.createElement("label");
      label.textContent = title;
      const hint = createHint(hintText);
      const area = document.createElement("textarea");
      area.rows = 4;
      area.value = JSON.stringify(config[key] || {}, null, 2);
      area.addEventListener("change", () => {
        try { config[key] = JSON.parse(area.value || "{}"); syncInspectorState(); }
        catch { toast("Ánh xạ phải là JSON object hợp lệ", true); area.value = JSON.stringify(config[key] || {}, null, 2); }
      });
      field.append(label, hint, area);
      panel.appendChild(field);
    });
    const depth = document.createElement("div");
    depth.className = "node-field";
    const depthLabel = document.createElement("label");
    depthLabel.textContent = "Thời gian chờ (giây)";
    const timeout = document.createElement("input");
    timeout.type = "number"; timeout.min = "0"; timeout.value = String(config.timeout ?? 300);
    timeout.addEventListener("change", () => { config.timeout = Number(timeout.value || 0); syncInspectorState(); });
    depth.append(depthLabel, timeout); panel.appendChild(depth);
    els.nodeForm.appendChild(panel);
  }

  function renderInstallApksForm(node) {
    const config = node.config || (node.config = {});
    if (!Array.isArray(config.apk_files)) config.apk_files = [];
    const panel = createInspectorPanel(
      "Cài APK theo thứ tự",
      "Chọn từng file APK. File được lưu trong dự án; node dùng ADB của phone đang kết nối và xác nhận package/version sau khi cài."
    );
    const list = document.createElement("div");
    list.className = "apk-install-list";
    config.apk_files.forEach((entry, index) => {
      const row = document.createElement("div");
      row.className = "apk-install-row";
      const label = document.createElement("span");
      label.textContent = `${index + 1}. ${entry.name || entry.asset_id || "APK"}`;
      label.title = entry.path || "";
      row.appendChild(label);
      [["↑", index - 1], ["↓", index + 1]].forEach(([caption, target]) => {
        const button = document.createElement("button");
        button.type = "button"; button.className = "secondary"; button.textContent = caption;
        button.disabled = target < 0 || target >= config.apk_files.length;
        button.addEventListener("click", () => {
          [config.apk_files[index], config.apk_files[target]] = [config.apk_files[target], config.apk_files[index]];
          syncInspectorState(); renderNodeForm(node);
        });
        row.appendChild(button);
      });
      const remove = document.createElement("button");
      remove.type = "button"; remove.className = "secondary"; remove.textContent = "Xóa";
      remove.addEventListener("click", () => {
        config.apk_files.splice(index, 1); syncInspectorState(); renderNodeForm(node);
      });
      row.appendChild(remove); list.appendChild(row);
    });
    panel.appendChild(list);
    const picker = document.createElement("input");
    picker.type = "file"; picker.accept = ".apk,application/vnd.android.package-archive";
    picker.multiple = true;
    picker.setAttribute("aria-label", "Chọn APK theo thứ tự cài");
    const status = document.createElement("p"); status.className = "field-help";
    status.textContent = "Thứ tự trong danh sách là thứ tự cài đặt.";
    picker.addEventListener("change", async () => {
      const files = Array.from(picker.files || []);
      if (config.apk_files.length + files.length > 50) { toast("Tối đa 50 APK mỗi node", true); picker.value = ""; return; }
      picker.disabled = true;
      for (const file of files) {
        status.textContent = `Đang lưu ${file.name}…`;
        try {
          const form = new FormData(); form.append("file", file, file.name);
          const saved = await api("/automation/phone/apks", { method: "POST", body: form });
          config.apk_files.push(saved); syncInspectorState();
          const item = document.createElement("div"); item.textContent = `${config.apk_files.length}. ${saved.name}`;
          list.appendChild(item);
        } catch (err) {
          toast(`Không lưu được ${file.name}: ${err.message}`, true);
        }
      }
      renderNodeForm(node);
    });
    panel.append(picker, status);
    const methodField = document.createElement("div"); methodField.className = "node-field";
    const methodLabel = document.createElement("label"); methodLabel.textContent = "Cách cài";
    const methodSelect = document.createElement("select");
    [["rtl_applications", "RTL Applications → Install App"], ["adb", "ADB qua Remote Debug Bridge"]].forEach(([value, title]) => {
      const option = document.createElement("option"); option.value = value; option.textContent = title;
      option.selected = (config.install_method || "rtl_applications") === value;
      methodSelect.appendChild(option);
    });
    methodSelect.addEventListener("change", () => { config.install_method = methodSelect.value; syncInspectorState(); });
    methodField.append(methodLabel, methodSelect); panel.appendChild(methodField);
    panel.appendChild(createTextField(node, "Biến chứa phone đã kết nối", "serial_variable", String(config.serial_variable || "artemis_phone"), { placeholder: "artemis_phone" }));
    panel.appendChild(createTextField(node, "Biến kết quả từng APK", "output_variable", String(config.output_variable || "phone_apk_install_results"), { placeholder: "phone_apk_install_results" }));
    panel.appendChild(createNumberField(node, "Thời gian tối đa mỗi APK (giây)", "install_timeout_seconds", Number(config.install_timeout_seconds || 180), { min: 10, max: 900, step: 1 }));
    appendSleepBeforeNodeField(panel, node, config);
    els.nodeForm.appendChild(panel);
  }

  function renderPhoneImageAssetField(node, required) {
    const config = node.config || (node.config = {});
    const panel = createInspectorPanel("Ảnh mẫu trên phone", "Tài sản được so khớp với ảnh chụp Android qua ARTEMIS. `Image search` vẫn dành riêng cho Chromium.");
    const field = document.createElement("div"); field.className = "node-field";
    const label = document.createElement("label"); label.textContent = "Ảnh mẫu";
    const select = document.createElement("select");
    const placeholder = document.createElement("option"); placeholder.value = ""; placeholder.textContent = "Chọn ảnh đã lưu"; select.appendChild(placeholder);
    state.phoneAssets.forEach((asset) => {
      const option = document.createElement("option"); option.value = asset.id;
      option.textContent = `${asset.name || "Phone image"} · ${asset.id}`;
      option.selected = String(config.image_asset_id || "") === String(asset.id); select.appendChild(option);
    });
    select.addEventListener("change", () => { config.image_asset_id = select.value; syncInspectorState(); renderPhoneAssetPreview(node, preview); });
    field.append(label, select);
    const preview = document.createElement("img"); preview.className = "phone-asset-preview"; preview.alt = "Ảnh mẫu phone";
    field.appendChild(preview); panel.appendChild(field);
    if (required && config.image_asset_id) renderPhoneAssetPreview(node, preview);
    const serialField = document.createElement("div"); serialField.className = "node-field";
    const serialLabel = document.createElement("label"); serialLabel.textContent = "ADB serial dùng để thử";
    const serialInput = document.createElement("input"); serialInput.type = "text";
    serialInput.value = String(localStorage.getItem("autoixb_phone_serial") || state.phoneRecording?.serial || "");
    serialInput.placeholder = "Chọn serial trong Ghi thao tác phone";
    serialField.append(serialLabel, serialInput); panel.appendChild(serialField);
    const result = document.createElement("p"); result.className = "field-help"; result.textContent = "Chưa thử so khớp."; panel.appendChild(result);
    const previewMatch = document.createElement("button"); previewMatch.type = "button"; previewMatch.className = "secondary"; previewMatch.textContent = "Thử tìm ảnh trên phone";
    previewMatch.disabled = !config.image_asset_id;
    previewMatch.addEventListener("click", async () => {
      const serial = String(serialInput.value || "").trim();
      if (!serial) { toast("Chọn ADB serial phone trước", true); return; }
      previewMatch.disabled = true; result.textContent = "Đang chụp và so khớp…";
      try {
        const options = { threshold: Number(config.threshold || 0.86), scale_min: Number(config.scale_min || 0.8), scale_max: Number(config.scale_max || 1.2), scale_steps: Number(config.scale_steps || 9), region: config.region || null };
        const match = await api(`/automation/phone/assets/${encodeURIComponent(config.image_asset_id)}/match`, { method: "POST", body: JSON.stringify({ serial, options }) });
        const status = match.found ? (match.ambiguous ? "Khớp chưa rõ, sẽ không chạm." : `Khớp ${(match.score * 100).toFixed(1)}% · tâm ${match.center.x}, ${match.center.y}`) : `Không khớp · ${(match.score * 100).toFixed(1)}%`;
        result.textContent = `${status} · chụp ${match.capture_ms} ms · tìm ${match.match_ms} ms`;
        if (match.preview_image_base64) {
          panel.querySelector(".phone-asset-match-wrap")?.remove();
          const matchImage = document.createElement("img"); matchImage.className = "phone-asset-match-preview";
          matchImage.alt = "Ảnh phone với vùng khớp dự kiến";
          matchImage.src = `data:image/png;base64,${match.preview_image_base64}`;
          const mark = document.createElement("span"); mark.className = "phone-asset-match-marker";
          if (match.bbox) {
            mark.style.left = `${(match.bbox.x / match.width) * 100}%`;
            mark.style.top = `${(match.bbox.y / match.height) * 100}%`;
            mark.style.width = `${(match.bbox.w / match.width) * 100}%`;
            mark.style.height = `${(match.bbox.h / match.height) * 100}%`;
          }
          const wrap = document.createElement("div"); wrap.className = "phone-asset-match-wrap";
          wrap.style.aspectRatio = `${match.width} / ${match.height}`;
          wrap.append(matchImage, mark); panel.appendChild(wrap);
        }
        localStorage.setItem("autoixb_phone_serial", serial);
      } catch (err) { result.textContent = err.message; }
      finally { previewMatch.disabled = !config.image_asset_id; }
    });
    panel.appendChild(previewMatch);
    els.nodeForm.prepend(panel);
  }

  async function renderPhoneAssetPreview(node, image) {
    const assetId = String(node.config?.image_asset_id || "");
    image.hidden = !assetId;
    if (!assetId) { image.removeAttribute("src"); return; }
    try { image.src = await phoneAssetUrl(assetId); } catch (_) { image.alt = "Không tải được ảnh mẫu"; }
  }

  async function phoneAssetUrl(assetId) {
    if (state.phoneAssetUrls.has(assetId)) return state.phoneAssetUrls.get(assetId);
    const headers = state.token ? { Authorization: `Bearer ${state.token}` } : {};
    const res = await fetch(`/automation/phone/assets/${encodeURIComponent(assetId)}`, { headers });
    if (!res.ok) throw new Error("Phone image asset could not be loaded.");
    const url = URL.createObjectURL(await res.blob()); state.phoneAssetUrls.set(assetId, url); return url;
  }

  function renderVariablesForm(node) {
    const tab = getInspectorTab(node.id);
    els.nodeForm.appendChild(buildInspectorTabs(node.id, tab));
    if (tab === "settings") {
      renderVariablesSettingsTab(node);
      return;
    }
    if (tab === "note") {
      renderNodeNoteTab(node);
      return;
    }
    renderVariablesOptionsTab(node);
  }

  function renderVariablesOptionsTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel(
      "Biến",
      "Node này đứng độc lập cạnh Start và chạy trước các node khác. Dùng biến dưới dạng {{ten_bien}}."
    );

    const constLabel = document.createElement("p");
    constLabel.className = "variables-subtitle";
    constLabel.textContent = "Biến hệ thống";
    panel.appendChild(constLabel);

    const constWrap = document.createElement("div");
    constWrap.className = "variables-constants";
    VARIABLE_CONSTANTS.forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "variables-constant-chip";
      chip.textContent = item.label;
      chip.title = `Dùng dưới dạng {{${item.key}}}`;
      constWrap.appendChild(chip);
    });
    panel.appendChild(constWrap);
    panel.appendChild(createHint("PHONE_SERIAL và PHONE_CONNECTION có sau khi phone kết nối; lượt chạy mới chỉ nạp lại nếu serial của đúng profile còn online."));

    const createWrap = document.createElement("div");
    createWrap.className = "variables-create-row";
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.placeholder = "ten_bien";
    const createBtn = document.createElement("button");
    createBtn.type = "button";
    createBtn.className = "secondary";
    createBtn.textContent = "+ Tạo biến";
    createBtn.addEventListener("click", () => {
      const rawName = String(nameInput.value || "").trim();
      if (!rawName) {
        toast("Vui lòng nhập tên biến", true);
        return;
      }
      const safeName = rawName.replace(/\s+/g, "_");
      const list = Array.isArray(config.custom_variables) ? config.custom_variables : [];
      if (list.some((it) => String(it?.name || "") === safeName)) {
        toast(`Biến '${safeName}' đã tồn tại`, true);
        return;
      }
      list.push({ name: safeName, source: "value", value: "", allow_override: true });
      config.custom_variables = list;
      node.config = config;
      syncVariablesRunInputs(node);
      renderNodeForm(node);
      syncInspectorState();
    });
    createWrap.appendChild(nameInput);
    createWrap.appendChild(createBtn);
    panel.appendChild(createWrap);

    const varsLabel = document.createElement("p");
    varsLabel.className = "variables-subtitle";
    varsLabel.textContent = "Biến tùy chỉnh";
    panel.appendChild(varsLabel);

    const table = document.createElement("div");
    table.className = "variables-table";
    const list = Array.isArray(config.custom_variables) ? config.custom_variables : [];
    if (!list.length) {
      const empty = document.createElement("div");
      empty.className = "variables-empty";
      empty.textContent = "Chưa có biến tùy chỉnh.";
      table.appendChild(empty);
    } else {
      list.forEach((item, idx) => {
        const row = document.createElement("div");
        row.className = "variables-row";
        item.source ||= "value";
        if (item.source === "value" && item.allow_override === undefined) item.allow_override = true;
        const save = (refresh = false) => {
          config.custom_variables = list;
          node.config = config;
          syncVariablesRunInputs(node);
          syncInspectorState();
          if (refresh) renderNodeForm(node);
        };
        const field = (caption, element) => {
          const label = document.createElement("label");
          const title = document.createElement("span"); title.textContent = caption;
          label.append(title, element); row.appendChild(label);
          return element;
        };
        const keyInput = document.createElement("input");
        keyInput.type = "text";
        keyInput.value = String(item?.name || "");
        keyInput.placeholder = "Tên biến";
        keyInput.addEventListener("change", () => {
          const next = String(keyInput.value || "").trim().replace(/\s+/g, "_");
          if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(next) || list.some((other, index) => index !== idx && other.name === next)) {
            keyInput.value = item.name; toast("Tên biến không hợp lệ hoặc đã tồn tại", true); return;
          }
          item.name = next; save();
        });
        field("Tên biến", keyInput);
        const source = document.createElement("select");
        [["value", "Giá trị cố định"], ["input", "Nhập khi chạy"], ["file", "CSV / XLSX"]].forEach(([value, label]) => {
          const option = document.createElement("option"); option.value = value; option.textContent = label; source.appendChild(option);
        });
        source.value = item.source;
        source.addEventListener("change", () => {
          item.source = source.value;
          if (item.source !== "value") delete item.value;
          if (item.source === "value") item.secret = false;
          save(true);
        });
        field("Nguồn", source);
        if (item.source === "value") {
          const value = document.createElement("input"); value.value = String(item.value ?? ""); value.placeholder = "Giá trị mặc định";
          value.addEventListener("change", () => { item.value = value.value; save(); });
          field("Giá trị", value);
          const override = document.createElement("input"); override.type = "checkbox"; override.checked = item.allow_override !== false;
          override.addEventListener("change", () => { item.allow_override = override.checked; save(); });
          field("Cho sửa khi chạy", override);
        } else if (item.source === "file") {
          const textField = (caption, key, placeholder, fallback = "") => {
            const input = document.createElement("input"); input.value = String(item[key] ?? fallback); input.placeholder = placeholder;
            input.addEventListener("change", () => { item[key] = input.value; save(); }); field(caption, input);
          };
          textField("Đường dẫn file trên máy chạy", "file_path", "D:\\data\\phone.csv");
          textField("Sheet (XLSX)", "sheet_name", "Để trống lấy sheet đầu");
          textField("Cột", "column", "Tên cột, A, B hoặc số cột");
          textField("Dòng dữ liệu", "row_index", "1", 1);
          textField("Biến chọn dòng khi chạy", "row_input", "Ví dụ data_row");
          const header = document.createElement("input"); header.type = "checkbox"; header.checked = item.has_header !== false;
          header.addEventListener("change", () => { item.has_header = header.checked; save(); }); field("Dòng đầu là tiêu đề", header);
        } else {
          const hint = document.createElement("small"); hint.textContent = `Giá trị ${item.name} sẽ hiện ở phần Đầu vào ứng dụng khi chạy.`;
          row.appendChild(hint);
        }
        if (item.source !== "value") {
          const secret = document.createElement("input"); secret.type = "checkbox"; secret.checked = Boolean(item.secret);
          secret.addEventListener("change", () => { item.secret = secret.checked; save(); }); field("Giá trị nhạy cảm", secret);
        }
        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "danger";
        delBtn.textContent = "x";
        delBtn.title = "Xóa biến";
        delBtn.addEventListener("click", () => {
          list.splice(idx, 1);
          save();
          renderNodeForm(node);
        });
        row.appendChild(delBtn);
        table.appendChild(row);
      });
    }
    panel.appendChild(table);
    els.nodeForm.appendChild(panel);
    syncVariablesRunInputs(node);
  }

  function syncVariablesRunInputs(node) {
    const config = node.config || {};
    const previous = new Set(Array.isArray(config.__managed_inputs) ? config.__managed_inputs : []);
    const desired = new Map();
    (Array.isArray(config.custom_variables) ? config.custom_variables : []).forEach((item) => {
      const name = String(item?.name || "").trim();
      if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(name)) return;
      const source = String(item.source || "value");
      if (source === "input") desired.set(String(item.input_name || name), { name: String(item.input_name || name), type: "string", required: true, secret: Boolean(item.secret) });
      if (source === "value" && item.allow_override !== false) desired.set(name, { name, type: "string", required: false, default: String(item.value ?? "") });
      const rowInput = String(item.row_input || "").trim();
      if (source === "file" && /^[A-Za-z_][A-Za-z0-9_]*$/.test(rowInput)) desired.set(rowInput, { name: rowInput, type: "number", required: false, default: Number(item.row_index || 1) });
    });
    state.inputs = (Array.isArray(state.inputs) ? state.inputs : []).filter((input) => !previous.has(input.name) && !desired.has(input.name));
    state.inputs.push(...desired.values());
    config.__managed_inputs = [...desired.keys()];
    renderAppRunInputs();
  }

  function renderVariablesSettingsTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel(
      "Cài đặt biến",
      "Thiết lập thời gian chờ và giới hạn thực thi cho node Biến."
    );
    appendSleepBeforeNodeField(panel, node, config);
    panel.appendChild(
      createNumberField(node, "Thời gian chờ node (giây)", "timeout", Number(config.timeout || 30), {
        min: 0,
        step: 1,
        hint: "Đặt 0 để tắt thời gian chờ.",
      })
    );
    panel.appendChild(
      createHint("Biến hệ thống `{{profile_id}}` và `{{profile_name}}` luôn có sẵn.")
    );
    els.nodeForm.appendChild(panel);
  }

  function renderGenericNodeForm(node) {
    const config = node.config || {};
    const keys = Object.keys(config).sort((a, b) => {
      if (a === "sleep_before_run_seconds" && b !== "sleep_before_run_seconds") return -1;
      if (b === "sleep_before_run_seconds" && a !== "sleep_before_run_seconds") return 1;
      return 0;
    });
    if (!keys.length) {
      els.nodeForm.innerHTML = "<div class='node-field'>Node chưa có trường cấu hình. Bạn có thể thêm ở bên dưới.</div>";
      return;
    }
    keys.forEach((key) => {
      if (key === "image_asset_id" && normaliseNodeType(node.type).startsWith("artemis_")) return;
      const value = config[key];
      const meta = fieldMeta(node, key);
      const field = document.createElement("div");
      field.className = "node-field";
      const label = document.createElement("label");
      label.textContent = meta.label;
      field.appendChild(label);
      if (meta.hint) {
        const hint = document.createElement("p");
        hint.className = "field-help";
        hint.textContent = meta.hint;
        field.appendChild(hint);
      }
      buildInputForField(node, key, value, field, meta);
      els.nodeForm.appendChild(field);
    });
  }

  function renderClickForm(node) {
    const tab = getInspectorTab(node.id);
    els.nodeForm.appendChild(buildInspectorTabs(node.id, tab));
    if (tab === "settings") {
      renderClickSettingsTab(node);
      return;
    }
    if (tab === "note") {
      renderNodeNoteTab(node);
      return;
    }
    renderClickOptionsTab(node);
  }

  function renderTypeTextForm(node) {
    const tab = getInspectorTab(node.id);
    els.nodeForm.appendChild(buildInspectorTabs(node.id, tab));
    if (tab === "settings") {
      renderTypeTextSettingsTab(node);
      return;
    }
    if (tab === "note") {
      renderNodeNoteTab(node);
      return;
    }
    renderTypeTextOptionsTab(node);
  }

  function renderOpenUrlForm(node) {
    const tab = getInspectorTab(node.id);
    els.nodeForm.appendChild(buildInspectorTabs(node.id, tab));
    if (tab === "settings") {
      renderOpenUrlSettingsTab(node);
      return;
    }
    if (tab === "note") {
      renderNodeNoteTab(node);
      return;
    }
    renderOpenUrlOptionsTab(node);
  }

  function renderElementExistForm(node) {
    const tab = getInspectorTab(node.id);
    els.nodeForm.appendChild(buildInspectorTabs(node.id, tab));
    if (tab === "settings") {
      renderElementExistSettingsTab(node);
      return;
    }
    if (tab === "note") {
      renderNodeNoteTab(node);
      return;
    }
    renderElementExistOptionsTab(node);
  }

  function renderOpenUrlOptionsTab(node) {
    const config = node.config || {};
    const waitFor = String(config.wait_for_navigation || "domcontentloaded").toLowerCase();
    const panel = createInspectorPanel(
      "Open URL options",
      "Điền URL rõ ràng, chọn điều kiện tải trang và thời gian chờ thêm."
    );
    panel.appendChild(
      createTextField(node, "URL", "url", String(config.url || ""), {
        placeholder: "https://genlogin.com",
        hint: "Đây là ô nhập link website cần mở.",
      })
    );
    panel.appendChild(
      createNumberField(node, "Wait time (milliseconds)", "wait_time_ms", Number(config.wait_time_ms || 0), {
        min: 0,
        step: 100,
        hint: "Sau khi trang báo loaded, chờ thêm để JS/render ổn định.",
      })
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Wait for navigation",
        "wait_for_navigation",
        ["load", "domcontentloaded", "networkidle0", "networkidle2"],
        waitFor
      )
    );
    panel.appendChild(
      createHint("Gợi ý: `DOMContentLoaded` thường nhanh; `Networkidle` phù hợp trang nặng JS.")
    );
    els.nodeForm.appendChild(panel);
  }

  function renderOpenUrlSettingsTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel("Cài đặt điều hướng", "Tùy chỉnh thời gian chờ khi mở URL.");
    appendSleepBeforeNodeField(panel, node, config);
    panel.appendChild(
      createNumberField(
        node,
        "Giới hạn tải trang (giây)",
        "navigation_timeout_seconds",
        Number(config.navigation_timeout_seconds || 90),
        { min: 5, step: 5 }
      )
    );
    panel.appendChild(
      createNumberField(node, "Thời gian chờ node (giây)", "timeout", Number(config.timeout || 120), {
        min: 5,
        step: 5,
        hint: "Timeout chung của node; nên lớn hơn navigation timeout.",
      })
    );
    els.nodeForm.appendChild(panel);
  }

  function renderElementExistOptionsTab(node) {
    const config = node.config || {};
    const selectorType = String(config.selector_type || "css").toLowerCase();
    const panel = createInspectorPanel(
      "Element Exist options",
      "Node trả nhánh `true/false` theo việc element có xuất hiện hay không."
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Selector type",
        "selector_type",
        ["css", "xpath", "text"],
        selectorType,
        { rerender: true }
      )
    );
    panel.appendChild(
      createTextField(node, "Selector", "selector", String(config.selector || ""), {
        placeholder: selectorPlaceholder(selectorType),
        hint: selectorHelp(selectorType),
      })
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Wait state",
        "wait_state",
        ["visible", "attached", "hidden", "detached"],
        String(config.wait_state || "visible").toLowerCase()
      )
    );
    panel.appendChild(
      createNumberField(node, "Timeout (seconds)", "timeout", Number(config.timeout || 5), {
        min: 1,
        step: 1,
      })
    );
    panel.appendChild(
      createTextField(
        node,
        "Output variable",
        "output_variable",
        String(config.output_variable || "exists"),
        { placeholder: "exists" }
      )
    );
    els.nodeForm.appendChild(panel);
  }

  function renderElementExistSettingsTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel("Branch behavior", "Nhánh output sau khi kiểm tra element.");
    appendSleepBeforeNodeField(panel, node, config);
    panel.appendChild(
      createHint("Tìm thấy element => đi theo edge `true`; không thấy => edge `false`.")
    );
    panel.appendChild(
      createHint("Biến output sẽ là boolean: true/false.")
    );
    els.nodeForm.appendChild(panel);
  }

  function renderGetTextForm(node) {
    const tab = getInspectorTab(node.id);
    els.nodeForm.appendChild(buildInspectorTabs(node.id, tab));
    if (tab === "settings") {
      renderGetTextSettingsTab(node);
      return;
    }
    if (tab === "note") {
      renderNodeNoteTab(node);
      return;
    }
    renderGetTextOptionsTab(node);
  }

  function renderGetValueForm(node) {
    const tab = getInspectorTab(node.id);
    els.nodeForm.appendChild(buildInspectorTabs(node.id, tab));
    if (tab === "settings") {
      renderGetValueSettingsTab(node);
      return;
    }
    if (tab === "note") {
      renderNodeNoteTab(node);
      return;
    }
    renderGetValueOptionsTab(node);
  }

  function renderSelectDropdownForm(node) {
    const tab = getInspectorTab(node.id);
    els.nodeForm.appendChild(buildInspectorTabs(node.id, tab));
    if (tab === "settings") {
      renderSelectDropdownSettingsTab(node);
      return;
    }
    if (tab === "note") {
      renderNodeNoteTab(node);
      return;
    }
    renderSelectDropdownOptionsTab(node);
  }

  function renderFileUploadForm(node) {
    const tab = getInspectorTab(node.id);
    els.nodeForm.appendChild(buildInspectorTabs(node.id, tab));
    if (tab === "settings") {
      renderFileUploadSettingsTab(node);
      return;
    }
    if (tab === "note") {
      renderNodeNoteTab(node);
      return;
    }
    renderFileUploadOptionsTab(node);
  }

  function renderGetTextOptionsTab(node) {
    const config = node.config || {};
    const selectorType = String(config.selector_type || "css").toLowerCase();
    const panel = createInspectorPanel(
      "Get Text options",
      "Lấy text từ element và lưu vào biến output."
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Selector type",
        "selector_type",
        ["css", "xpath", "text"],
        selectorType,
        { rerender: true }
      )
    );
    panel.appendChild(
      createTextField(node, "Selector", "selector", String(config.selector || ""), {
        placeholder: selectorPlaceholder(selectorType),
        hint: selectorHelp(selectorType),
      })
    );
    panel.appendChild(
      createTextField(
        node,
        "Output variable",
        "output_variable",
        String(config.output_variable || "text"),
        { placeholder: "text_result" }
      )
    );
    els.nodeForm.appendChild(panel);
  }

  function renderGetTextSettingsTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel("Extraction settings", "Tùy chỉnh khi đọc text.");
    appendSleepBeforeNodeField(panel, node, config);
    panel.appendChild(
      createNumberField(node, "Timeout (seconds)", "timeout", Number(config.timeout || 10), {
        min: 1,
        step: 1,
      })
    );
    panel.appendChild(
      createBooleanField(
        node,
        "Trim whitespace",
        "trim_output",
        config.trim_output !== false,
        "Bật để tự động bỏ khoảng trắng đầu/cuối trong kết quả text."
      )
    );
    els.nodeForm.appendChild(panel);
  }

  function renderGetValueOptionsTab(node) {
    const config = node.config || {};
    const selectorType = String(config.selector_type || "css").toLowerCase();
    const panel = createInspectorPanel(
      "Get Value options",
      "Lấy giá trị `value` từ input/select/textarea."
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Selector type",
        "selector_type",
        ["css", "xpath", "text"],
        selectorType,
        { rerender: true }
      )
    );
    panel.appendChild(
      createTextField(node, "Selector", "selector", String(config.selector || ""), {
        placeholder: selectorPlaceholder(selectorType),
        hint: selectorHelp(selectorType),
      })
    );
    panel.appendChild(
      createTextField(
        node,
        "Output variable",
        "output_variable",
        String(config.output_variable || "value"),
        { placeholder: "input_value" }
      )
    );
    els.nodeForm.appendChild(panel);
  }

  function renderGetValueSettingsTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel("Read settings", "Tùy chỉnh khi đọc value.");
    appendSleepBeforeNodeField(panel, node, config);
    panel.appendChild(
      createNumberField(node, "Timeout (seconds)", "timeout", Number(config.timeout || 10), {
        min: 1,
        step: 1,
      })
    );
    panel.appendChild(
      createBooleanField(
        node,
        "Trim whitespace",
        "trim_output",
        config.trim_output !== false,
        "Bật để chuẩn hóa output value trước khi lưu biến."
      )
    );
    els.nodeForm.appendChild(panel);
  }

  function renderSelectDropdownOptionsTab(node) {
    const config = node.config || {};
    const selectorType = String(config.selector_type || "css").toLowerCase();
    const optionBy = String(config.select_option_by || "value").toLowerCase();
    const panel = createInspectorPanel(
      "Select Dropdown options",
      "Chọn option trong dropdown theo value, label hoặc index."
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Selector type",
        "selector_type",
        ["css", "xpath", "text"],
        selectorType,
        { rerender: true }
      )
    );
    panel.appendChild(
      createTextField(node, "Selector", "selector", String(config.selector || ""), {
        placeholder: selectorPlaceholder(selectorType),
        hint: selectorHelp(selectorType),
      })
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Select option by",
        "select_option_by",
        ["value", "label", "index"],
        optionBy,
        { rerender: true }
      )
    );
    if (optionBy === "index") {
      panel.appendChild(
        createNumberField(node, "Option index", "option_index", Number(config.option_index || 0), {
          min: 0,
          step: 1,
          hint: "Index bắt đầu từ 0.",
        })
      );
    } else if (optionBy === "label") {
      panel.appendChild(
        createTextField(node, "Option label", "option_label", String(config.option_label || ""), {
          placeholder: "Vietnam",
        })
      );
    } else {
      panel.appendChild(
        createTextField(node, "Option value", "option_value", String(config.option_value || ""), {
          placeholder: "vn",
        })
      );
    }
    els.nodeForm.appendChild(panel);
  }

  function renderSelectDropdownSettingsTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel("Select settings", "Điều chỉnh timeout khi chọn option.");
    appendSleepBeforeNodeField(panel, node, config);
    panel.appendChild(
      createNumberField(node, "Timeout (seconds)", "timeout", Number(config.timeout || 10), {
        min: 1,
        step: 1,
      })
    );
    els.nodeForm.appendChild(panel);
  }

  function renderFileUploadOptionsTab(node) {
    const config = node.config || {};
    const selectorType = String(config.selector_type || "css").toLowerCase();
    const fileType = String(config.file_type || "file").toLowerCase();
    const panel = createInspectorPanel(
      "File Upload options",
      "Upload file local, base64 hoặc URL image vào input file."
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Selector type",
        "selector_type",
        ["css", "xpath", "text"],
        selectorType,
        { rerender: true }
      )
    );
    panel.appendChild(
      createTextField(node, "Selector", "selector", String(config.selector || ""), {
        placeholder: selectorPlaceholder(selectorType),
        hint: selectorHelp(selectorType),
      })
    );
    panel.appendChild(
      createChoiceField(
        node,
        "File type",
        "file_type",
        ["file", "base64", "url image"],
        fileType,
        { rerender: true }
      )
    );
    if (fileType === "base64") {
      panel.appendChild(
        createTextareaField(node, "Base64 data", "file_path", String(config.file_path || ""), {
          rows: 4,
          placeholder: "data:...;base64,AAA...",
          hint: "Có thể dán full data URL hoặc chuỗi base64 thuần.",
        })
      );
      panel.appendChild(
        createTextField(node, "Filename", "filename", String(config.filename || "upload.bin"), {
          placeholder: "upload.bin",
        })
      );
    } else if (fileType === "url image") {
      panel.appendChild(
        createTextField(node, "Image URL", "file_path", String(config.file_path || ""), {
          placeholder: "https://example.com/avatar.png",
        })
      );
      panel.appendChild(
        createTextField(node, "Filename", "filename", String(config.filename || "image.png"), {
          placeholder: "image.png",
        })
      );
    } else {
      panel.appendChild(
        createTextField(node, "File path", "file_path", String(config.file_path || ""), {
          placeholder: "C:\\\\data\\\\avatar.png",
          hint: "Đường dẫn file local trên máy chạy automation.",
        })
      );
    }
    panel.appendChild(
      createTextField(
        node,
        "Output variable",
        "output_variable",
        String(config.output_variable || "uploaded_file"),
        { placeholder: "uploaded_file" }
      )
    );
    els.nodeForm.appendChild(panel);
  }

  function renderFileUploadSettingsTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel("Upload settings", "Điều chỉnh timeout khi chờ input file.");
    appendSleepBeforeNodeField(panel, node, config);
    panel.appendChild(
      createNumberField(node, "Timeout (seconds)", "timeout", Number(config.timeout || 30), {
        min: 1,
        step: 1,
      })
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Wait state",
        "wait_state",
        ["attached", "visible"],
        String(config.wait_state || "attached").toLowerCase()
      )
    );
    els.nodeForm.appendChild(panel);
  }

  function renderClickOptionsTab(node) {
    const config = node.config || {};
    const buttonValue = String(config.button || "left").toLowerCase();
    const selectBy = String(config.select_by || "selector").toLowerCase();
    const selectorType = String(config.selector_type || "css").toLowerCase();

    const panel = createInspectorPanel("Click options", "Thiết lập cách click nhanh và trực quan.");
    panel.appendChild(
      createChoiceField(node, "Button", "button", ["left", "right", "center"], buttonValue)
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Select by",
        "select_by",
        ["selector", "coordinates"],
        selectBy,
        { rerender: true }
      )
    );

    if (selectBy === "coordinates") {
      panel.appendChild(
        createNumberField(node, "X", "x", Number(config.x || 0), {
          placeholder: "120",
          hint: "Vị trí X trên trang",
        })
      );
      panel.appendChild(
        createNumberField(node, "Y", "y", Number(config.y || 0), {
          placeholder: "240",
          hint: "Vị trí Y trên trang",
        })
      );
      panel.appendChild(
        createHint("Chế độ tọa độ sẽ ưu tiên x/y khi chạy node Click.")
      );
    } else {
      panel.appendChild(
        createChoiceField(
          node,
          "Selector type",
          "selector_type",
          ["css", "xpath", "text"],
          selectorType,
          { rerender: true }
        )
      );
      panel.appendChild(
        createTextField(node, "Selector", "selector", String(config.selector || ""), {
          placeholder: selectorPlaceholder(selectorType),
          hint: selectorHelp(selectorType),
        })
      );
    }

    panel.appendChild(
      createNumberField(node, "Click count", "click_count", Number(config.click_count || 1), {
        min: 1,
        step: 1,
      })
    );
    panel.appendChild(
      createNumberField(node, "Timeout (seconds)", "timeout", Number(config.timeout || 10), {
        min: 1,
        step: 1,
      })
    );
    els.nodeForm.appendChild(panel);
  }

  function renderClickSettingsTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel("Execution settings", "Tùy chọn nâng cao khi click.");
    appendSleepBeforeNodeField(panel, node, config);
    panel.appendChild(
      createBooleanField(
        node,
        "Force click",
        "force",
        Boolean(config.force),
        "Bỏ qua trạng thái che phủ và cố click element."
      )
    );
    panel.appendChild(
      createHint("Mẹo: nếu trang dynamic, hãy tăng timeout thay vì bật force ngay.")
    );
    els.nodeForm.appendChild(panel);
  }

  function renderTypeTextOptionsTab(node) {
    const config = node.config || {};
    const inputMode = String(config.input_mode || "selector").toLowerCase();
    const selectorType = String(config.selector_type || "css").toLowerCase();

    const panel = createInspectorPanel(
      "Type Text options",
      "Nhập text theo selector hoặc gõ trực tiếp vào active page."
    );
    panel.appendChild(
      createChoiceField(
        node,
        "Type into",
        "input_mode",
        ["selector", "active_page"],
        inputMode,
        { rerender: true }
      )
    );

    if (inputMode === "selector") {
      panel.appendChild(
        createChoiceField(
          node,
          "Selector type",
          "selector_type",
          ["css", "xpath", "text"],
          selectorType,
          { rerender: true }
        )
      );
      panel.appendChild(
        createTextField(node, "Selector", "selector", String(config.selector || ""), {
          placeholder: selectorPlaceholder(selectorType),
          hint: selectorHelp(selectorType),
        })
      );
      panel.appendChild(
        createChoiceField(
          node,
          "Input strategy",
          "fill",
          ["fill", "type"],
          config.fill === false ? "type" : "fill",
          { valueMap: { fill: true, type: false } }
        )
      );
    } else {
      panel.appendChild(
        createHint("Active page mode: text sẽ gõ vào vị trí con trỏ hiện tại.")
      );
    }

    panel.appendChild(
      createTextareaField(node, "Text", "text", String(config.text || ""), {
        placeholder: "Nhập text hoặc dùng biến {{otp_code}}",
      })
    );
    els.nodeForm.appendChild(panel);
  }

  function renderTypeTextSettingsTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel("Typing settings", "Điều chỉnh tốc độ và timeout.");
    appendSleepBeforeNodeField(panel, node, config);
    panel.appendChild(
      createNumberField(node, "Delay (ms)", "delay_ms", Number(config.delay_ms || 25), {
        min: 0,
        step: 5,
      })
    );
    panel.appendChild(
      createNumberField(node, "Timeout (seconds)", "timeout", Number(config.timeout || 10), {
        min: 1,
        step: 1,
      })
    );
    els.nodeForm.appendChild(panel);
  }

  function ensureCommonExecutionDefaults(node) {
    const config = node.config || {};
    const defaultSeconds = normaliseNodeType(node.type).startsWith("artemis") ? 1 : 2;
    if (typeof config.sleep_before_run_seconds === "undefined") {
      config.sleep_before_run_seconds = defaultSeconds;
    }
    if (!Number.isFinite(Number(config.sleep_before_run_seconds))) {
      config.sleep_before_run_seconds = defaultSeconds;
    }
    node.config = config;
  }

  function appendSleepBeforeNodeField(panel, node, config) {
    const current = Number(config.sleep_before_run_seconds);
    const value = Number.isFinite(current) ? current : (normaliseNodeType(node.type).startsWith("artemis") ? 1 : 2);
    panel.appendChild(
      createNumberField(
        node,
        "Chờ trước khi chạy node (giây, 0 để bỏ qua)",
        "sleep_before_run_seconds",
        value,
        { min: 0, step: 0.1 }
      )
    );
  }

  function renderNodeNoteTab(node) {
    const config = node.config || {};
    const panel = createInspectorPanel("Node note", "Ghi chú nhanh cho node này.");
    panel.appendChild(
      createTextareaField(node, "Note", "__note", String(config.__note || ""), {
        rows: 4,
        placeholder: "Ví dụ: Node này dùng để nhập email đăng ký.",
      })
    );
    els.nodeForm.appendChild(panel);
  }

  function createInspectorPanel(title, description) {
    const panel = document.createElement("section");
    panel.className = "inspector-panel";
    const h = document.createElement("h4");
    h.textContent = UI_TEXT_VI[title] || title;
    panel.appendChild(h);
    if (description) {
      const p = document.createElement("p");
      p.className = "inspector-help";
      p.textContent = UI_TEXT_VI[description] || description;
      panel.appendChild(p);
    }
    return panel;
  }

  function buildInspectorTabs(nodeId, activeTab) {
    const wrap = document.createElement("div");
    wrap.className = "inspector-tabs";
    [
      { id: "options", label: "Tùy chọn" },
      { id: "settings", label: "Cài đặt" },
      { id: "note", label: "Ghi chú" },
    ].forEach((tab) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "inspector-tab" + (activeTab === tab.id ? " active" : "");
      btn.textContent = tab.label;
      btn.addEventListener("click", () => {
        state.inspectorTabByNodeId[nodeId] = tab.id;
        const node = getEditableNode(nodeId);
        if (node) {
          renderNodeForm(node);
          syncInspectorState();
        }
      });
      wrap.appendChild(btn);
    });
    return wrap;
  }

  function getInspectorTab(nodeId) {
    return state.inspectorTabByNodeId[nodeId] || "options";
  }

  function fieldMeta(node, key) {
    const selectorType = String(node?.config?.selector_type || "css").toLowerCase();
    const nodeType = normaliseNodeType(node?.type || "");
    if (key === "selector") {
      return {
        label: FIELD_LABELS[key] || key,
        hint: selectorHelp(selectorType),
        placeholder: selectorPlaceholder(selectorType),
      };
    }
    if (key === "url") {
      return {
        label: FIELD_LABELS[key] || key,
        hint: DEFAULT_FIELD_HINTS[key],
        placeholder: "https://example.com",
      };
    }
    if (key === "file_path" && nodeType === "file_upload") {
      const fileType = String(node?.config?.file_type || "file").toLowerCase();
      if (fileType === "base64") {
        return {
          label: "Base64 data",
          hint: "Dán chuỗi base64 hoặc data URL.",
          placeholder: "data:...;base64,AAA...",
        };
      }
      if (fileType === "url image") {
        return {
          label: "Image URL",
          hint: "URL ảnh cần tải và upload vào input file.",
          placeholder: "https://example.com/image.png",
        };
      }
      return {
        label: "File path",
        hint: "Đường dẫn file local trên máy chạy automation.",
        placeholder: "C:\\data\\avatar.png",
      };
    }
    return {
      label: FIELD_LABELS[key] || humanizeKey(key),
      hint: DEFAULT_FIELD_HINTS[key] || "",
      placeholder: "",
    };
  }

  function selectorHelp(selectorType) {
    if (selectorType === "xpath") {
      return "XPath selector. Ví dụ: //button[contains(.,'Login')]";
    }
    if (selectorType === "text") {
      return "Text selector. Ví dụ: Login hoặc Sign in";
    }
    return "CSS selector. Ví dụ: button.login hoặc input[name='email']";
  }

  function selectorPlaceholder(selectorType) {
    if (selectorType === "xpath") return "//div[@id='main']//button[1]";
    if (selectorType === "text") return "Login";
    return "button.login";
  }

  function humanizeKey(key) {
    return String(key || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function choiceLabel(value) {
    const map = {
      domcontentloaded: "DOMContentLoaded",
      networkidle0: "Networkidle0",
      networkidle2: "Networkidle2",
      active_page: "Trang hiện tại",
      left: "Trái",
      right: "Phải",
      center: "Giữa",
      selector: "Bộ chọn phần tử",
      coordinates: "Tọa độ",
      visible: "Hiển thị",
      attached: "Đã gắn vào trang",
      hidden: "Ẩn",
      detached: "Đã gỡ khỏi trang",
      value: "Giá trị",
      label: "Nhãn",
      index: "Vị trí",
      fill: "Điền nội dung",
      type: "Gõ từng ký tự",
    };
    const key = String(value || "").toLowerCase();
    if (map[key]) return map[key];
    return String(value || "").replace(/_/g, " ");
  }

  function createFieldShell(labelText, hint) {
    const field = document.createElement("div");
    field.className = "node-field";
    const label = document.createElement("label");
    label.textContent = UI_TEXT_VI[labelText] || labelText;
    field.appendChild(label);
    if (hint) {
      const hintEl = document.createElement("p");
      hintEl.className = "field-help";
      hintEl.textContent = UI_TEXT_VI[hint] || hint;
      field.appendChild(hintEl);
    }
    return field;
  }

  function createHint(message) {
    const hint = document.createElement("p");
    hint.className = "field-hint";
    hint.textContent = UI_TEXT_VI[message] || message;
    return hint;
  }

  function createChoiceField(node, labelText, key, options, currentValue, extras = {}) {
    const field = createFieldShell(labelText, extras.hint);
    const group = document.createElement("div");
    group.className = "choice-group";
    options.forEach((opt) => {
      const optionLabel = document.createElement("label");
      optionLabel.className = "choice-pill";
      const value = extras.valueMap ? extras.valueMap[opt] : opt;
      const checked = String(currentValue) === String(opt);
      if (checked) optionLabel.classList.add("active");
      optionLabel.innerHTML = `
        <input type="radio" name="${escapeHtml(node.id + ":" + key)}" value="${escapeHtml(opt)}" ${checked ? "checked" : ""} />
        <span>${escapeHtml(choiceLabel(opt))}</span>
      `;
      const input = optionLabel.querySelector("input");
      input.addEventListener("change", () => {
        if (!input.checked) return;
        if (key === "select_by" && value === "selector") {
          delete node.config.x;
          delete node.config.y;
        }
        if (key === "input_mode" && value === "active_page") {
          delete node.config.selector;
        }
        if (key === "select_option_by") {
          delete node.config.option_value;
          delete node.config.option_label;
          delete node.config.option_index;
          if (value === "index") {
            node.config.option_index = 0;
          } else if (value === "label") {
            node.config.option_label = "";
          } else {
            node.config.option_value = "";
          }
        }
        if (key === "file_type") {
          if (value === "file") {
            delete node.config.filename;
          } else if (!node.config.filename) {
            node.config.filename = value === "url image" ? "image.png" : "upload.bin";
          }
        }
        node.config[key] = value;
        syncInspectorState();
        if (extras.rerender) {
          renderNodeForm(node);
          syncInspectorState();
        }
      });
      group.appendChild(optionLabel);
    });
    field.appendChild(group);
    return field;
  }

  function createTextField(node, labelText, key, currentValue, extras = {}) {
    const field = createFieldShell(labelText, extras.hint);
    const isXpathSelector = key === "selector" && String(node?.config?.selector_type || "").toLowerCase() === "xpath";
    if (isXpathSelector) {
      field.classList.add("node-field-selector-xpath");
      const area = document.createElement("textarea");
      area.rows = 3;
      area.value = currentValue;
      if (extras.placeholder) area.placeholder = extras.placeholder;
      area.addEventListener("change", () => {
        node.config[key] = area.value;
        syncInspectorState();
      });
      field.appendChild(area);
      return field;
    }
    const input = document.createElement("input");
    input.type = "text";
    input.value = currentValue;
    if (extras.placeholder) input.placeholder = extras.placeholder;
    input.addEventListener("change", () => {
      node.config[key] = input.value;
      syncInspectorState();
    });
    field.appendChild(input);
    return field;
  }

  function createTextareaField(node, labelText, key, currentValue, extras = {}) {
    const field = createFieldShell(labelText, extras.hint);
    if (key === "text") field.classList.add("node-field-data-text");
    const area = document.createElement("textarea");
    area.rows = key === "text" ? Math.max(extras.rows || 3, 5) : extras.rows || 3;
    area.value = currentValue;
    if (extras.placeholder) area.placeholder = extras.placeholder;
    area.addEventListener("change", () => {
      node.config[key] = area.value;
      syncInspectorState();
    });
    field.appendChild(area);
    return field;
  }

  function createNumberField(node, labelText, key, currentValue, extras = {}) {
    const field = createFieldShell(labelText, extras.hint);
    const input = document.createElement("input");
    input.type = "number";
    input.value = Number.isFinite(currentValue) ? String(currentValue) : "0";
    if (typeof extras.min !== "undefined") input.min = String(extras.min);
    if (typeof extras.max !== "undefined") input.max = String(extras.max);
    if (typeof extras.step !== "undefined") input.step = String(extras.step);
    if (extras.placeholder) input.placeholder = extras.placeholder;
    input.addEventListener("change", () => {
      node.config[key] = Number(input.value || 0);
      syncInspectorState();
    });
    field.appendChild(input);
    return field;
  }

  function createBooleanField(node, labelText, key, currentValue, hintText) {
    const field = createFieldShell(labelText, hintText);
    const wrap = document.createElement("div");
    wrap.className = "node-field-bool";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = Boolean(currentValue);
    const text = document.createElement("span");
    text.textContent = checkbox.checked ? "true" : "false";
    checkbox.addEventListener("change", () => {
      node.config[key] = checkbox.checked;
      text.textContent = checkbox.checked ? "true" : "false";
      syncInspectorState();
    });
    wrap.appendChild(checkbox);
    wrap.appendChild(text);
    field.appendChild(wrap);
    return field;
  }

  function ensureClickDefaults(node) {
    const config = node.config || {};
    if (!config.button) config.button = "left";
    if (!config.selector_type) config.selector_type = "css";
    if (typeof config.timeout === "undefined") config.timeout = 10;
    if (typeof config.force === "undefined") config.force = false;
    if (typeof config.click_count === "undefined") config.click_count = 1;
    if (!config.select_by) {
      config.select_by = typeof config.x !== "undefined" && typeof config.y !== "undefined"
        ? "coordinates"
        : "selector";
    }
    if (config.select_by === "selector" && !config.selector) config.selector = "button";
    node.config = config;
  }

  function ensureOpenUrlDefaults(node) {
    const config = node.config || {};
    if (!config.url) config.url = "https://example.com";
    if (!config.wait_for_navigation) config.wait_for_navigation = "domcontentloaded";
    if (typeof config.wait_time_ms === "undefined") {
      const settleSeconds = Number(config.settle_seconds || 0);
      config.wait_time_ms = Number.isFinite(settleSeconds) ? Math.max(0, Math.round(settleSeconds * 1000)) : 0;
    }
    if (typeof config.navigation_timeout_seconds === "undefined") {
      config.navigation_timeout_seconds = 90;
    }
    if (typeof config.timeout === "undefined") config.timeout = 120;
    node.config = config;
  }

  function ensureElementExistDefaults(node) {
    const config = node.config || {};
    if (!config.selector_type) config.selector_type = "css";
    if (!config.selector) config.selector = "body";
    if (!config.wait_state) config.wait_state = "visible";
    if (typeof config.timeout === "undefined") config.timeout = 5;
    if (!config.output_variable) config.output_variable = "exists";
    node.config = config;
  }

  function ensureGetTextDefaults(node) {
    const config = node.config || {};
    if (!config.selector_type) config.selector_type = "css";
    if (!config.selector) config.selector = "body";
    if (typeof config.timeout === "undefined") config.timeout = 10;
    if (typeof config.trim_output === "undefined") config.trim_output = true;
    if (!config.output_variable) config.output_variable = "text";
    node.config = config;
  }

  function ensureGetValueDefaults(node) {
    const config = node.config || {};
    if (!config.selector_type) config.selector_type = "css";
    if (!config.selector) config.selector = "input";
    if (typeof config.timeout === "undefined") config.timeout = 10;
    if (typeof config.trim_output === "undefined") config.trim_output = true;
    if (!config.output_variable) config.output_variable = "value";
    node.config = config;
  }

  function ensureSelectDropdownDefaults(node) {
    const config = node.config || {};
    if (!config.selector_type) config.selector_type = "css";
    if (!config.selector) config.selector = "select";
    if (!config.select_option_by) {
      if (typeof config.option_label !== "undefined") {
        config.select_option_by = "label";
      } else if (typeof config.option_index !== "undefined") {
        config.select_option_by = "index";
      } else {
        config.select_option_by = "value";
      }
    }
    if (config.select_option_by === "index") {
      if (typeof config.option_index === "undefined") config.option_index = 0;
    } else if (config.select_option_by === "label") {
      if (typeof config.option_label === "undefined") config.option_label = "";
    } else if (typeof config.option_value === "undefined") {
      config.option_value = "1";
    }
    if (typeof config.timeout === "undefined") config.timeout = 10;
    node.config = config;
  }

  function ensureFileUploadDefaults(node) {
    const config = node.config || {};
    if (!config.selector_type) config.selector_type = "css";
    if (!config.selector) config.selector = "input[type=file]";
    if (!config.file_type) config.file_type = "file";
    if (typeof config.file_path === "undefined") config.file_path = "";
    if (!config.filename) config.filename = "upload.bin";
    if (typeof config.timeout === "undefined") config.timeout = 30;
    if (!config.wait_state) config.wait_state = "attached";
    if (!config.output_variable) config.output_variable = "uploaded_file";
    node.config = config;
  }

  function ensureTypeTextDefaults(node) {
    const config = node.config || {};
    if (typeof config.text === "undefined") config.text = "";
    if (typeof config.delay_ms === "undefined") config.delay_ms = 25;
    if (typeof config.timeout === "undefined") config.timeout = 10;
    if (typeof config.fill === "undefined") config.fill = true;
    if (!config.input_mode) {
      config.input_mode = config.selector ? "selector" : "active_page";
    }
    if (config.input_mode === "selector") {
      if (!config.selector_type) config.selector_type = "css";
      if (!config.selector) config.selector = "input";
    } else {
      delete config.selector;
    }
    node.config = config;
  }

  function ensureVariablesDefaults(node) {
    const config = node.config || {};
    if (!Array.isArray(config.custom_variables)) {
      config.custom_variables = [];
    }
    if (typeof config.timeout === "undefined") {
      config.timeout = 30;
    }
    node.config = config;
  }

  function normaliseNodeType(value) {
    const aliases = {
      typetext: "type_text",
      type_text: "type_text",
      click: "click",
      openurl: "open_url",
      element_exists: "element_exist",
      gettext: "get_text",
      getvalue: "get_value",
      selectdropdown: "select_dropdown",
      fileupload: "file_upload",
    };
    const key = String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[()\-:/.]/g, " ")
      .replace(/\s+/g, "_");
    return aliases[key] || key;
  }

  function buildInputForField(node, key, value, container, meta = {}) {
    if (key === "selector" && String(node?.config?.selector_type || "").toLowerCase() === "xpath") {
      container.classList.add("node-field-selector-xpath");
      const area = document.createElement("textarea");
      area.rows = 3;
      area.value = String(value ?? "");
      if (meta.placeholder) area.placeholder = meta.placeholder;
      area.addEventListener("change", () => {
        node.config[key] = area.value;
        syncInspectorState();
      });
      container.appendChild(area);
      return;
    }
    const selectOptions = SELECT_OPTIONS[key];
    if (selectOptions) {
      const select = document.createElement("select");
      selectOptions.forEach((opt) => {
        const option = document.createElement("option");
        option.value = opt;
        option.textContent = opt;
        option.selected = String(value) === String(opt);
        select.appendChild(option);
      });
      select.addEventListener("change", () => {
        node.config[key] = select.value;
        syncInspectorState();
        if (key === "selector_type") {
          renderNodeForm(node);
          syncInspectorState();
        }
      });
      container.appendChild(select);
      return;
    }

    if (typeof value === "boolean") {
      const wrap = document.createElement("div");
      wrap.className = "node-field-bool";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = value;
      checkbox.addEventListener("change", () => {
        node.config[key] = checkbox.checked;
        syncInspectorState();
      });
      const text = document.createElement("span");
      text.textContent = checkbox.checked ? "true" : "false";
      checkbox.addEventListener("change", () => {
        text.textContent = checkbox.checked ? "true" : "false";
      });
      wrap.appendChild(checkbox);
      wrap.appendChild(text);
      container.appendChild(wrap);
      return;
    }

    if (typeof value === "number") {
      const input = document.createElement("input");
      input.type = "number";
      input.value = String(value);
      input.addEventListener("change", () => {
        node.config[key] = Number(input.value || 0);
        syncInspectorState();
      });
      container.appendChild(input);
      return;
    }

    if (Array.isArray(value) || isPlainObject(value)) {
      const area = document.createElement("textarea");
      area.rows = 4;
      area.value = JSON.stringify(value, null, 2);
      area.addEventListener("change", () => {
        try {
          node.config[key] = JSON.parse(area.value);
          syncInspectorState();
        } catch (err) {
          toast(`Invalid JSON for '${key}'`, true);
          area.value = JSON.stringify(node.config[key], null, 2);
        }
      });
      container.appendChild(area);
      return;
    }

    if (typeof value === "string") {
      const isLong = LONG_TEXT_KEYS.includes(key) || value.length > 60 || value.includes("\n");
      if (isLong) {
        if (key === "text") container.classList.add("node-field-data-text");
        const area = document.createElement("textarea");
        area.rows = key === "text" ? 5 : 3;
        area.value = value;
        if (meta.placeholder) area.placeholder = meta.placeholder;
        area.addEventListener("change", () => {
          node.config[key] = area.value;
          syncInspectorState();
        });
        container.appendChild(area);
      } else {
        const input = document.createElement("input");
        input.type = "text";
        input.value = value;
        if (meta.placeholder) input.placeholder = meta.placeholder;
        input.addEventListener("change", () => {
          node.config[key] = input.value;
          syncInspectorState();
        });
        container.appendChild(input);
      }
      return;
    }

    const fallback = document.createElement("input");
    fallback.type = "text";
    fallback.value = String(value ?? "");
    fallback.addEventListener("change", () => {
      node.config[key] = fallback.value;
      syncInspectorState();
    });
    container.appendChild(fallback);
  }

  function addConfigField() {
    const node = getEditableNode(state.selectedNodeId);
    if (!node) {
      toast("Select a node first", true);
      return;
    }
    const key = els.newConfigKey.value.trim();
    if (!key) {
      toast("Key is required", true);
      return;
    }
    const valueRaw = els.newConfigValue.value.trim();
    node.config[key] = parseSmartValue(valueRaw);
    els.newConfigKey.value = "";
    els.newConfigValue.value = "";
    renderNodeForm(node);
    syncInspectorState();
  }

  function syncInspectorState() {
    const node = getEditableNode(state.selectedNodeId);
    if (!node) return;
    els.nodeConfigEditor.value = JSON.stringify(node.config || {}, null, 2);
  }

  function applyNodeConfig() {
    const node = getEditableNode(state.selectedNodeId);
    if (!node) {
      toast("Select a node first", true);
      return;
    }
    try {
      const parsed = JSON.parse(els.nodeConfigEditor.value || "{}");
      if (!isPlainObject(parsed)) throw new Error("Node config must be a JSON object");
      node.config = parsed;
      renderNodeForm(node);
      syncInspectorState();
      toast("JSON đã áp dụng vào bản nháp. Bấm Lưu node để cập nhật sơ đồ.");
    } catch (err) {
      toast("Invalid JSON config", true);
    }
  }

  function removeSelectedNode() {
    if (!state.selectedNodeId) return;
    removeNodeById(state.selectedNodeId);
  }

  function removeNodeById(nodeId) {
    const id = String(nodeId || "").trim();
    if (!id) return;
    if (state.openNodePropertiesId === id) closeNodeProperties();
    state.nodes = state.nodes.filter((n) => n.id !== id);
    state.edges = state.edges.filter((e) => e.from !== id && e.to !== id);
    delete state.inspectorTabByNodeId[id];
    if (state.selectedNodeId === id) {
      state.selectedNodeId = null;
    }
    if (state.runningSingleNodeId === id) {
      state.runningSingleNodeId = null;
    }
    renderCanvas();
    renderEdgeList();
    renderNodeInspector();
  }

  function renderEdgeList() {
    els.edgeList.innerHTML = "";
    state.edges.forEach((edge, idx) => {
      const row = document.createElement("div");
      row.className = "edge-row";
      row.innerHTML = `
        <span>${escapeHtml(edge.from)} -> ${escapeHtml(edge.to)}</span>
        <select></select>
        <button class="danger">x</button>
      `;
      const select = row.querySelector("select");
      EDGE_LABELS.forEach((label) => {
        const option = document.createElement("option");
        option.value = label;
        option.textContent = label;
        option.selected = edge.label === label;
        select.appendChild(option);
      });
      select.addEventListener("change", () => {
        edge.label = select.value;
        renderCanvas();
      });
      row.querySelector("button").addEventListener("click", () => {
        removeEdgeAt(idx);
      });
      els.edgeList.appendChild(row);
    });
  }

  async function saveApp() {
    const name = els.appName.value.trim();
    if (!name) {
      toast("Nhập tên ứng dụng trước khi lưu", true);
      return false;
    }
    const payload = {
      name,
      description: els.appDesc.value.trim(),
      graph: { nodes: state.nodes, edges: state.edges, inputs: state.inputs },
    };
    let saved;
    if (state.currentAppId) {
      saved = await api(`/automation/apps/${state.currentAppId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      toast("App updated");
    } else {
      saved = await api("/automation/apps", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.currentAppId = saved.id;
      toast("App created");
    }
    await refreshApps();
    await selectApp(saved.id);
    return true;
  }

  async function refreshApps() {
    state.apps = await api("/automation/apps");
    renderAppList();
  }

  function renderAppList() {
    renderAppHome();
    renderAppTabs();
  }

  function appLastViewedMap() {
    try {
      const value = JSON.parse(localStorage.getItem("ix_app_last_viewed") || "{}");
      return value && typeof value === "object" ? value : {};
    } catch {
      return {};
    }
  }

  function renderAppHome() {
    if (!els.appHomeRecent) return;
    const query = String(els.appHomeSearch?.value || "").trim().toLowerCase();
    const viewed = appLastViewedMap();
    const apps = state.apps
      .filter((app) => !query || String(app.name || "").toLowerCase().includes(query))
      .slice()
      .sort((a, b) => Number(viewed[b.id] || 0) - Number(viewed[a.id] || 0));
    els.appHomeRecent.replaceChildren();
    els.appHomeEmpty.hidden = apps.length !== 0;
    els.appHomeRecent.hidden = apps.length === 0;
    const emptyTitle = els.appHomeEmpty.querySelector("h3");
    const emptyCopy = els.appHomeEmpty.querySelector("p");
    if (emptyTitle && emptyCopy) {
      const noMatches = Boolean(query && state.apps.length);
      emptyTitle.textContent = noMatches ? "Không tìm thấy ứng dụng" : "Chưa có ứng dụng";
      emptyCopy.textContent = noMatches ? "Thử từ khóa khác để tìm trong các ứng dụng đã lưu." : "Tạo ứng dụng đầu tiên để bắt đầu dựng luồng tự động hóa.";
    }
    apps.forEach((app) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "recent-app-row";
      const viewedAt = Number(viewed[app.id] || 0);
      row.innerHTML = `
        <span class="recent-app-icon" aria-hidden="true">◇</span>
        <span class="recent-app-main"><strong>${escapeHtml(app.name || "Ứng dụng chưa đặt tên")}</strong><small>v${escapeHtml(app.version ?? 1)} · ${escapeHtml(String(app.graph?.nodes?.length ?? "Workflow"))} ${app.graph?.nodes ? "node" : ""}</small></span>
        <span class="recent-app-last-view">${viewedAt ? timeAgo(viewedAt / 1000) : timeAgo(app.updated_at)}</span>
        <span class="recent-app-open" aria-hidden="true">›</span>`;
      row.addEventListener("click", () => selectApp(app.id).catch((err) => toast(err.message, true)));
      els.appHomeRecent.appendChild(row);
    });
  }

  function renderAppTabs() {
    const openApps = state.openAppIds
      .map((id) => state.apps.find((app) => String(app.id) === String(id)))
      .filter(Boolean);
    [els.appHomeTabs, els.appEditorTabs].forEach((container) => {
      if (!container) return;
      const isHomeTabs = container === els.appHomeTabs;
      if (isHomeTabs) container.hidden = openApps.length === 0;
      container.replaceChildren();
      openApps.forEach((app) => {
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = "app-session-tab" + (String(app.id) === String(state.currentAppId) ? " active" : "");
        tab.innerHTML = `<span class="app-tab-icon" aria-hidden="true">◇</span><span>${escapeHtml(app.name)}</span><span class="app-tab-close" aria-hidden="true">×</span>`;
        tab.addEventListener("click", (event) => {
          if (event.target.closest(".app-tab-close")) {
            state.openAppIds = state.openAppIds.filter((id) => String(id) !== String(app.id));
            localStorage.setItem("ix_app_editor_tabs", JSON.stringify(state.openAppIds));
            renderAppTabs();
            if (String(state.currentAppId) === String(app.id)) goToAppHome();
            return;
          }
          selectApp(app.id).catch((err) => toast(err.message, true));
        });
        container.appendChild(tab);
      });
      if (state.appEditorView === "editor" && !state.currentAppId) {
        const draft = document.createElement("span");
        draft.className = "app-session-tab active draft-tab";
        draft.innerHTML = '<span class="app-tab-icon" aria-hidden="true">◇</span><span>Ứng dụng mới</span>';
        container.appendChild(draft);
      }
      if (!isHomeTabs) {
        const add = document.createElement("button");
        add.type = "button";
        add.className = "app-session-add";
        add.textContent = "+";
        add.title = "Tạo ứng dụng mới";
        add.setAttribute("aria-label", "Tạo ứng dụng mới");
        add.addEventListener("click", startNewApp);
        container.appendChild(add);
      }
    });
  }

  async function selectApp(appId) {
    const app = await api(`/automation/apps/${appId}`);
    state.currentAppId = app.id;
    const id = String(app.id);
    state.openAppIds = [...state.openAppIds.filter((openId) => String(openId) !== id), id].slice(-6);
    localStorage.setItem("ix_app_editor_tabs", JSON.stringify(state.openAppIds));
    const lastViewed = appLastViewedMap();
    lastViewed[id] = Date.now();
    localStorage.setItem("ix_app_last_viewed", JSON.stringify(lastViewed));
    els.appName.value = app.name || "";
    els.appDesc.value = app.description || "";
    els.appVersion.textContent = `v${Number(app.version) || 1}.0.0`;
    state.nodes = (app.graph?.nodes || []).map((n) => ({
      id: n.id,
      type: n.type,
      config: n.config || state.defaultsByType[n.type] || {},
      x: Number(n.x || 0),
      y: Number(n.y || 0),
    }));
    state.edges = (app.graph?.edges || []).map((e) => ({
      from: e.from || e.from_node,
      to: e.to,
      label: e.label || "next",
    }));
    state.inputs = app.graph?.inputs || [];
    state.selectedNodeId = null;
    state.inspectorTabByNodeId = {};
    renderAppList();
    renderCanvas();
    renderNodeInspector();
    renderAppRunInputs();
    renderEdgeList();
    setAppEditorView("editor");
  }

  async function deleteCurrentApp() {
    if (!state.currentAppId) {
      toast("No app selected", true);
      return;
    }
    if (!confirm("Delete current app?")) return;
    await api(`/automation/apps/${state.currentAppId}`, { method: "DELETE" });
    toast("App deleted");
    state.openAppIds = state.openAppIds.filter((id) => String(id) !== String(state.currentAppId));
    localStorage.setItem("ix_app_editor_tabs", JSON.stringify(state.openAppIds));
    newGraph();
    await refreshApps();
    goToAppHome();
  }
  async function saveTask() {
    if (!state.currentAppId) {
      toast("Save app first", true);
      return;
    }
    const name = els.taskName.value.trim();
    if (!name) {
      toast("Task name required", true);
      return;
    }
    await api("/automation/tasks", {
      method: "POST",
      body: JSON.stringify({
        name,
        app_id: state.currentAppId,
        default_inputs: {},
        profile_selector: selectorPayload(),
        concurrency: 3,
        retry: 0,
        timeout: 300,
        stop_on_error: false,
        close_profile_on_finish: false,
      }),
    });
    toast("Task saved");
    await refreshTasks();
  }

  async function refreshTasks() {
    state.tasks = await api("/automation/tasks");
    renderTaskList();
  }

  function renderTaskList() {
    els.taskList.innerHTML = "";
    state.tasks.forEach((task) => {
      const item = document.createElement("div");
      item.className = "list-item";
      item.innerHTML = `<strong>${escapeHtml(task.name)}</strong><br /><small>${escapeHtml(task.id)} | app ${escapeHtml(task.app_id)}</small>`;

      const actions = document.createElement("div");
      actions.style.display = "flex";
      actions.style.gap = "6px";
      actions.style.marginTop = "6px";

      const runBtn = document.createElement("button");
      runBtn.className = "secondary";
      runBtn.textContent = "Run";
      runBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const run = await api(`/automation/tasks/${task.id}/run`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        toast("Task run: " + run.run_id);
        selectRun(run.run_id);
      });

      const delBtn = document.createElement("button");
      delBtn.className = "danger";
      delBtn.textContent = "Delete";
      delBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        await api(`/automation/tasks/${task.id}`, { method: "DELETE" });
        toast("Task deleted");
        await refreshTasks();
      });

      actions.appendChild(runBtn);
      actions.appendChild(delBtn);
      item.appendChild(actions);
      els.taskList.appendChild(item);
    });
  }

  function currentGraphPayload() {
    return {
      nodes: state.nodes.map((n) => ({
        id: n.id,
        type: n.type,
        config: n.config || {},
        x: Number(n.x || 0),
        y: Number(n.y || 0),
      })),
      edges: state.edges.map((e) => ({
        from: e.from,
        to: e.to,
        label: e.label || "next",
      })),
      inputs: state.inputs || [],
    };
  }

  async function runCurrentApp() {
    if (!state.currentAppId) {
      toast("Save or select app first", true);
      return;
    }
    if (["queued", "pending", "running"].includes(String(state.currentRunStatus).toLowerCase())) return;

    state.currentRunId = null;
    state.currentRunStatus = "pending";
    state.runStopRequested = false;
    syncRunButtonState();
    syncSelectedProfilesToInput();
    try {
      const inputs = collectAppInputValues();
      const run = await api("/automation/runs", {
        method: "POST",
        body: JSON.stringify({
          app_id: state.currentAppId,
          inputs,
          profile_selector: selectorPayload(),
          concurrency: 1,
          retry: 0,
          timeout: 300,
          stop_on_error: true,
          close_profile_on_finish: false,
        }),
      });
      toast("Run created: " + run.run_id);
      switchTab("builder");
      selectRun(run.run_id);
    } catch (err) {
      state.currentRunStatus = "";
      syncRunButtonState();
      syncSelectedProfilesToInput();
      toast("Could not start app: " + err.message, true);
    }
  }

  function renderAppRunInputs() {
    if (!els.appRunInputs) return;
    els.appRunInputs.replaceChildren();
    const inputs = Array.isArray(state.inputs) ? state.inputs : [];
    els.appRunInputs.hidden = inputs.length === 0;
    if (!inputs.length) return;
    const heading = document.createElement("strong"); heading.textContent = "Đầu vào ứng dụng"; els.appRunInputs.appendChild(heading);
    inputs.forEach((item) => {
      const name = String(item?.name || "").trim(); if (!name) return;
      const row = document.createElement("label"); row.className = "app-run-input-row";
      const title = document.createElement("span"); title.textContent = `${name}${item.required ? " *" : ""}`;
      let input;
      if (String(item.type || "string") === "boolean") {
        input = document.createElement("input"); input.type = "checkbox"; input.checked = Boolean(item.default);
      } else {
        input = document.createElement("input"); input.type = item.secret ? "password" : (String(item.type) === "number" ? "number" : "text");
        input.value = item.default == null ? "" : String(item.default); input.autocomplete = item.secret ? "new-password" : "off";
      }
      input.dataset.appInput = name; input.dataset.inputType = String(item.type || "string"); input.dataset.required = String(Boolean(item.required));
      row.append(title, input); els.appRunInputs.appendChild(row);
    });
  }

  function collectAppInputValues() {
    const values = {};
    els.appRunInputs.querySelectorAll("[data-app-input]").forEach((input) => {
      let value = input.type === "checkbox" ? input.checked : input.value;
      if (input.dataset.inputType === "number" && value !== "") value = Number(value);
      if (input.dataset.required === "true" && (value === "" || value === null || value === undefined)) {
        throw new Error(`Cần nhập giá trị cho ${input.dataset.appInput}.`);
      }
      if (value !== "") values[input.dataset.appInput] = value;
    });
    return values;
  }

  function syncRunButtonState() {
    const running = ["queued", "pending", "running", "stopping"].includes(
      String(state.currentRunStatus || "").toLowerCase()
    );
    els.runAppBtn.classList.toggle("is-running", running);
    els.runAppBtn.disabled = running;
    els.runAppBtn.setAttribute("aria-busy", String(running));
    els.runAppIcon.textContent = running ? "⟳" : "▶";
    els.runAppLabel.textContent = running ? "Đang chạy..." : "Chạy thử ứng dụng";
    const stopping = running && Boolean(state.runStopRequested);
    const canStop = running && Boolean(state.currentRunId) && !stopping;
    els.runAppStopBtn.disabled = !canStop;
    els.runAppStopBtn.textContent = stopping ? "Đang dừng..." : "■ Dừng ứng dụng";
    byId("stopRunBtn").disabled = !canStop;
    byId("stopRunBtn").textContent = stopping ? "Đang dừng..." : "Dừng";
  }

  async function runSingleNode(nodeId, singleNodeOnly = false) {
    const targetNodeId = String(nodeId || "").trim();
    if (!targetNodeId) {
      toast("Invalid node id", true);
      return;
    }
    if (!state.currentAppId) {
      toast("Save or select app first", true);
      return;
    }
    if (state.runningSingleNodeId) {
      toast("Another single-node run is in progress", true);
      return;
    }
    const node = state.nodes.find((n) => n.id === targetNodeId);
    if (!node) {
      toast("Node not found", true);
      return;
    }
    state.runningSingleNodeId = targetNodeId;
    renderCanvas();
    try {
      const run = await api("/automation/runs", {
        method: "POST",
        body: JSON.stringify({
          app_id: state.currentAppId,
          graph: currentGraphPayload(),
          start_node_id: targetNodeId,
          single_node_only: singleNodeOnly,
          inputs: collectAppInputValues(),
          profile_selector: selectorPayload(),
          concurrency: 1,
          retry: 0,
          timeout: 300,
          stop_on_error: false,
          close_profile_on_finish: false,
        }),
      });
      state.currentRunStatus = "pending";
      syncSelectedProfilesToInput();
      toast(`${singleNodeOnly ? "Thử riêng" : "Chạy từ"} ${node.type}: ${run.run_id}`);
      selectRun(run.run_id);
    } finally {
      state.runningSingleNodeId = null;
      renderCanvas();
    }
  }

  async function loadProfilesForPicker(options = {}) {
    if (state.profilePickerLoading) return;
    state.profilePickerLoading = true;
    els.loadProfilesBtn.disabled = true;
    els.reloadProfilesBtn.disabled = true;
    els.loadProfilesBtn.textContent = "Loading...";
    renderProfilePickerList();
    try {
      const groupId = Number(els.groupId.value || 0);
      const tagId = Number(els.tagId.value || 0);
      const limit = 100;
      let page = 1;
      const all = [];
      while (true) {
        const data = await api(
          `/profiles?group_id=${groupId}&tag_id=${tagId}&page=${page}&limit=${limit}`
        );
        const batch = Array.isArray(data?.profiles) ? data.profiles : [];
        all.push(...batch);
        if (batch.length < limit) break;
        page += 1;
        if (page > 100) break;
      }
      const uniqueById = new Map();
      all.forEach((p) => {
        if (!p?.profile_id) return;
        uniqueById.set(String(p.profile_id), {
          profile_id: String(p.profile_id),
          name: String(p.name || ""),
          tags: Array.isArray(p.tags) ? p.tags : [],
        });
      });
      state.loadedProfiles = Array.from(uniqueById.values()).sort((a, b) => {
        return (a.name || a.profile_id).localeCompare(b.name || b.profile_id);
      });
      state.profileListPage = 1;
      const validIds = new Set(state.loadedProfiles.map((p) => p.profile_id));
      state.selectedProfileIds = state.selectedProfileIds.filter((id) => validIds.has(id));
      renderProfilePickerList();
      syncSelectedProfilesToInput();
      if (!options.silent) toast(`Loaded ${state.loadedProfiles.length} profiles`);
    } finally {
      state.profilePickerLoading = false;
      els.loadProfilesBtn.disabled = false;
      els.reloadProfilesBtn.disabled = false;
      els.loadProfilesBtn.textContent = "Load Profiles";
      renderProfilePickerList();
    }
  }

  function renderProfilePickerList() {
    els.profilePickerList.innerHTML = "";
    if (state.profilePickerLoading) {
      els.profilePickerList.innerHTML = "<div class='profile-picker-empty'>Loading profiles...</div>";
      els.profilePrevPageBtn.disabled = true;
      els.profileNextPageBtn.disabled = true;
      els.profilePageLabel.textContent = "...";
      return;
    }
    if (!state.loadedProfiles.length) {
      els.profilePickerList.innerHTML =
        "<div class='profile-picker-empty'>Click 'Load Profiles' to fetch current IXBrowser profiles.</div>";
      els.profilePrevPageBtn.disabled = true;
      els.profileNextPageBtn.disabled = true;
      els.profilePageLabel.textContent = "0/0";
      return;
    }
    const visible = filteredProfiles();
    if (!visible.length) {
      els.profilePickerList.innerHTML =
        "<div class='profile-picker-empty'>No profiles matched your search.</div>";
      els.profilePrevPageBtn.disabled = true;
      els.profileNextPageBtn.disabled = true;
      els.profilePageLabel.textContent = "0/0";
      return;
    }
    const pageSize = clampProfilePageSize(state.profilePageSize);
    state.profilePageSize = pageSize;
    if (els.profilePageSize.value !== String(pageSize)) {
      els.profilePageSize.value = String(pageSize);
    }
    const totalPages = Math.max(1, Math.ceil(visible.length / pageSize));
    state.profileListPage = Math.max(1, Math.min(state.profileListPage, totalPages));
    const start = (state.profileListPage - 1) * pageSize;
    const pageItems = visible.slice(start, start + pageSize);
    els.profilePrevPageBtn.disabled = state.profileListPage <= 1;
    els.profileNextPageBtn.disabled = state.profileListPage >= totalPages;
    els.profilePageLabel.textContent = `${state.profileListPage}/${totalPages}`;
    const selected = new Set(state.selectedProfileIds);
    pageItems.forEach((profile) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "profile-row" + (selected.has(profile.profile_id) ? " selected" : "");
      row.innerHTML = `
        <span class="profile-row-dot"></span>
        <div class="profile-row-meta">
          <div class="profile-row-title">${escapeHtml(profile.name || "(No name)")}</div>
          <div class="profile-row-sub">${escapeHtml(profile.profile_id)}</div>
        </div>
        <span class="profile-row-check">${selected.has(profile.profile_id) ? "✓" : ""}</span>
      `;
      row.addEventListener("click", () => {
        const checked = !selected.has(profile.profile_id);
        toggleProfileSelection(profile.profile_id, checked);
        renderProfilePickerList();
      });
      els.profilePickerList.appendChild(row);
    });
  }

  function filteredProfiles() {
    const query = String(els.profileSearch.value || "")
      .trim()
      .toLowerCase();
    if (!query) return state.loadedProfiles.slice();
    return state.loadedProfiles.filter((profile) => {
      const hay = `${profile.profile_id} ${profile.name} ${(profile.tags || []).join(" ")}`
        .toLowerCase();
      return hay.includes(query);
    });
  }

  function toggleProfileSelection(profileId, checked) {
    const set = new Set(state.selectedProfileIds);
    if (checked) {
      set.add(profileId);
    } else {
      set.delete(profileId);
    }
    state.selectedProfileIds = Array.from(set);
    syncSelectedProfilesToInput();
  }

  function selectAllVisibleProfiles() {
    const set = new Set(state.selectedProfileIds);
    filteredProfiles().forEach((profile) => set.add(profile.profile_id));
    state.selectedProfileIds = Array.from(set);
    syncSelectedProfilesToInput();
    renderProfilePickerList();
  }

  function clearProfileSelection() {
    state.selectedProfileIds = [];
    syncSelectedProfilesToInput();
    renderProfilePickerList();
  }

  function changeProfilePage(delta) {
    const visible = filteredProfiles();
    const totalPages = Math.max(1, Math.ceil(visible.length / clampProfilePageSize(state.profilePageSize)));
    state.profileListPage = Math.max(1, Math.min(totalPages, state.profileListPage + delta));
    renderProfilePickerList();
  }

  function clampProfilePageSize(value) {
    const size = Number(value);
    if (!Number.isFinite(size)) return 12;
    return Math.max(1, Math.min(100, Math.floor(size)));
  }

  function updateProfilePageSize(value) {
    const size = clampProfilePageSize(value);
    state.profilePageSize = size;
    localStorage.setItem("automation_profile_page_size", String(size));
    state.profileListPage = 1;
    renderProfilePickerList();
  }

  function syncSelectedProfilesToInput() {
    const clean = Array.from(
      new Set(
        state.selectedProfileIds
          .map((s) => String(s || "").trim())
          .filter(Boolean)
      )
    );
    state.selectedProfileIds = clean;
    els.profileIds.value = clean.join(",");
    const totalLoaded = state.loadedProfiles.length;
    if (!clean.length) {
      els.selectedProfilesSummary.innerHTML = totalLoaded
        ? `Chưa chọn profile <span class="small">(chạy theo nhóm/thẻ)</span>`
        : "Chưa chọn profile";
      return;
    }
    const statusRaw = String(state.currentRunStatus || "");
    const statusBadge = statusRaw
      ? ` <span class="small">| ${escapeHtml(statusRaw)}</span>`
      : "";
    const strong = `<span class="profile-summary-strong">Đã chọn ${clean.length}</span>`;
    if (clean.length === 1) {
      const profile = state.loadedProfiles.find((p) => p.profile_id === clean[0]);
      const name = profile?.name || clean[0];
      els.selectedProfilesSummary.innerHTML =
        `<span class="profile-summary-strong">${escapeHtml(name)}</span> <span class="small">${escapeHtml(clean[0])}</span>${statusBadge}`;
      return;
    }
    els.selectedProfilesSummary.innerHTML = totalLoaded
      ? `${strong} <span class="small">/ ${totalLoaded} đã tải</span>${statusBadge}`
      : `${strong}${statusBadge}`;
  }

  function selectorPayload() {
    const ids = (els.profileIds.value || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    return {
      profile_ids: ids.length ? ids : null,
      group_id: Number(els.groupId.value || 0),
      tag_id: Number(els.tagId.value || 0),
    };
  }

  function stopExternalRunDiscovery() {
    if (state.runDiscoveryTimer) {
      clearInterval(state.runDiscoveryTimer);
      state.runDiscoveryTimer = null;
    }
  }

  function syncExternalRunDiscovery() {
    stopExternalRunDiscovery();
    if (!state.currentAppId || state.appEditorView !== "editor") return;
    state.runDiscoverySince = Date.now() / 1000;

    const discover = async () => {
      if (state.runPollTimer) return;
      const runs = await api("/automation/runs?limit=40");
      const appRuns = runs.filter((run) => String(run.app_id) === String(state.currentAppId));
      const activeRun = appRuns.find((run) => ["queued", "pending", "running"].includes(String(run.status || "").toLowerCase()));
      const recentRun = appRuns.find((run) => Number(run.created_at || 0) >= state.runDiscoverySince);
      const candidate = activeRun || recentRun;
      if (candidate && String(candidate.id) !== String(state.currentRunId)) {
        selectRun(candidate.id);
      }
    };

    discover().catch((err) => console.warn("External run discovery failed:", err));
    state.runDiscoveryTimer = setInterval(() => {
      discover().catch((err) => console.warn("External run discovery failed:", err));
    }, 1800);
  }

  function selectRun(runId) {
    state.currentRunId = runId;
    state.currentRunStatus = "";
    state.runStopRequested = false;
    syncSelectedProfilesToInput();
    monitorRun(runId).catch((err) => toast(err.message, true));
  }

  function updateRunNodeElement(nodeId) {
    const id = String(nodeId || "");
    if (!id) return;
    const element = els.canvas.querySelector(`[data-node-id="${CSS.escape(id)}"]`);
    if (!element) return;
    const isError = state.runFailedNodeIds.has(id);
    const isActive = state.runActiveNodeId === id && !isError;
    element.classList.toggle("run-active", isActive);
    element.classList.toggle("run-error", isError);
    updateNodeStepBadge(id);
  }

  function clearRunNodeHighlights() {
    state.runActiveNodeId = null;
    state.runFailedNodeIds.clear();
    state.runNodeStepIndices.clear();
    state.runStepCounter = 0;
    // Reset badges from the previous run as well as stale highlight classes.
    els.canvas.querySelectorAll(".node").forEach((element) => {
      element.classList.remove("run-active", "run-error");
      updateNodeStepBadge(element.dataset.nodeId);
    });
  }

  function setRunNodeActive(nodeId) {
    const id = String(nodeId || "");
    if (!id) return;
    const previousId = state.runActiveNodeId;
    if (state.runFailedNodeIds.delete(id)) updateRunNodeElement(id);
    state.runActiveNodeId = id;
    if (previousId && previousId !== id) updateRunNodeElement(previousId);
    updateRunNodeElement(id);
  }

  function setRunNodeFailed(nodeId) {
    const id = String(nodeId || "");
    if (!id) return;
    const previousActiveId = state.runActiveNodeId;
    state.runActiveNodeId = null;
    state.runFailedNodeIds.add(id);
    if (previousActiveId && previousActiveId !== id) updateRunNodeElement(previousActiveId);
    updateRunNodeElement(id);
  }

  function applyRunNodeLogs(logs) {
    logs.forEach((log) => {
      const nodeId = String(log.node_id || "");
      if (!nodeId) return;
      const message = String(log.message || "");
      const data = log.data && typeof log.data === "object" ? log.data : {};
      const node = state.nodes.find((candidate) => String(candidate.id) === nodeId);
      const nodeType = data.node_type || node?.type || "";
      if (/^Node started:/i.test(message) || data.event === "node_started") {
        if (isStepIndexExcludedNodeType(nodeType)) {
          log.display_step = null;
        } else {
          state.runStepCounter += 1;
          state.runNodeStepIndices.set(nodeId, state.runStepCounter);
          log.display_step = state.runStepCounter;
          updateNodeStepBadge(nodeId);
        }
        setRunNodeActive(nodeId);
      } else if (String(log.level || "").toLowerCase() === "error") {
        log.display_step = state.runNodeStepIndices.get(nodeId) ?? null;
        setRunNodeFailed(nodeId);
      } else if (data.event === "node_succeeded" || data.event === "node_failed" || data.event === "node_cancelled") {
        log.display_step = state.runNodeStepIndices.get(nodeId) ?? null;
        if (data.event === "node_failed") setRunNodeFailed(nodeId);
        if (data.event === "node_cancelled" && state.runActiveNodeId === nodeId) {
          state.runActiveNodeId = null;
          updateRunNodeElement(nodeId);
        }
      }
    });
  }

  function applyRunResultErrors(run) {
    (run?.items || []).forEach((item) => {
      (item?.result?.nodes || []).forEach((nodeResult) => {
        if (String(nodeResult?.status || "").toLowerCase() === "failed") {
          setRunNodeFailed(nodeResult.node_id);
        }
      });
    });
  }

  function formatRunLogLine(log) {
    const tm = new Date(log.ts * 1000).toLocaleTimeString();
    const node = log.node_id ? `[${log.node_id}] ` : "";
    const lines = [`[${tm}] ${String(log.level || "info").toUpperCase()} ${node}${log.message || ""}`];
    const data = log.data && typeof log.data === "object" ? log.data : {};
    const event = String(data.event || "");
    const fields = Array.isArray(data.config_fields) ? data.config_fields.join(", ") : "";

    if (event === "node_started") {
      if (log.display_step != null) lines.push(`    Step: ${log.display_step}`);
      if (data.page_url) lines.push(`    Page: ${data.page_url}`);
      if (fields) lines.push(`    Config fields: ${fields}`);
    } else if (event === "node_succeeded") {
      if (log.display_step != null) lines.push(`    Step: ${log.display_step}`);
      if (data.duration_ms != null) lines.push(`    Duration: ${data.duration_ms} ms`);
      if (data.next_label) lines.push(`    Branch: ${data.next_label}`);
      if (data.outputs && Object.keys(data.outputs).length) {
        let outputText = "";
        try { outputText = JSON.stringify(data.outputs); } catch { outputText = String(data.outputs); }
        if (outputText.length > 3500) outputText = outputText.slice(0, 3500) + "… [truncated]";
        lines.push(`    Outputs: ${outputText}`);
      }
      if (Array.isArray(data.capability_flags) && data.capability_flags.length) {
        lines.push(`    Capability notes: ${data.capability_flags.join(", ")}`);
      }
    } else if (event === "node_failed") {
      if (log.display_step != null) lines.push(`    Step: ${log.display_step}`);
      if (data.error_type) lines.push(`    Error type: ${data.error_type}`);
      if (data.duration_ms != null) lines.push(`    Duration before failure: ${data.duration_ms} ms`);
      if (data.page_url) lines.push(`    Page: ${data.page_url}`);
      if (fields) lines.push(`    Config fields: ${fields}`);
      if (data.traceback) lines.push(`    Traceback:\n${String(data.traceback).split("\n").map((line) => `      ${line}`).join("\n")}`);
    } else if (event === "node_cancelled") {
      if (log.display_step != null) lines.push(`    Step: ${log.display_step}`);
      if (data.duration_ms != null) lines.push(`    Duration before stop: ${data.duration_ms} ms`);
    }
    return lines.join("\n");
  }

  async function monitorRun(runId) {
    els.runDock.open = true;
    if (state.runPollTimer) {
      clearInterval(state.runPollTimer);
      state.runPollTimer = null;
    }
    clearRunNodeHighlights();
    let lastLogId = 0;
    els.runLogs.textContent = "";

    let tickInProgress = false;
    const tick = async () => {
      if (tickInProgress) return;
      tickInProgress = true;
      try {
        const run = await api(`/automation/runs/${runId}`);
        state.currentRunStatus = String(run.status || "");
        state.runStopRequested = Boolean(state.runStopRequested || run.stop_requested);
        syncRunButtonState();
        syncSelectedProfilesToInput();

        // Drain every available page. On a terminal run, the last request can
        // still have more than 200 records, so stopping after that page loses
        // final node events and makes the log look truncated.
        const renderedPages = [];
        let logs = [];
        do {
          logs = await api(`/automation/runs/${runId}/logs?after_id=${lastLogId}&limit=200`);
          if (!logs.length) break;
          lastLogId = logs[logs.length - 1].id;
          applyRunNodeLogs(logs);
          renderedPages.push(logs.map(formatRunLogLine).join("\n"));
        } while (logs.length === 200);

        if (renderedPages.length) {
          const followOutput =
            els.runLogs.scrollHeight - els.runLogs.scrollTop - els.runLogs.clientHeight < 8;
          const newText = renderedPages.join("\n");
          els.runLogs.textContent += (els.runLogs.textContent ? "\n" : "") + newText;
          if (followOutput) els.runLogs.scrollTop = els.runLogs.scrollHeight;
        }

        if (["done", "failed", "cancelled"].includes(run.status)) {
          applyRunResultErrors(run);
          const previousActiveId = state.runActiveNodeId;
          state.runActiveNodeId = null;
          if (previousActiveId) updateRunNodeElement(previousActiveId);
          state.currentRunStatus = String(run.status || "");
          syncSelectedProfilesToInput();
          clearInterval(state.runPollTimer);
          state.runPollTimer = null;
        }
      } finally {
        tickInProgress = false;
      }
    };

    await tick();
    state.runPollTimer = setInterval(() => {
      tick().catch((err) => {
        clearInterval(state.runPollTimer);
        state.runPollTimer = null;
        toast("Run monitor failed: " + err.message, true);
      });
    }, 2000);
  }

  function refreshCurrentRunLog() {
    if (!state.currentRunId) {
      toast("Chưa có lần chạy để tải log", true);
      return;
    }
    monitorRun(state.currentRunId).catch((err) => toast(err.message, true));
  }

  async function stopCurrentRun() {
    if (!state.currentRunId) {
      toast("Chưa có lượt chạy đang hoạt động", true);
      return;
    }
    const active = ["queued", "pending", "running", "stopping"].includes(
      String(state.currentRunStatus || "").toLowerCase()
    );
    if (!active || state.runStopRequested) return;

    state.runStopRequested = true;
    syncRunButtonState();
    try {
      const result = await api(`/automation/runs/${state.currentRunId}/stop`, { method: "POST" });
      if (result.already_finished) {
        state.currentRunStatus = String(result.status || "done");
        state.runStopRequested = false;
        syncRunButtonState();
        toast("Lượt chạy đã kết thúc");
        return;
      }
      toast("Đang dừng ứng dụng; node hiện tại sẽ bị ngắt và các node sau sẽ không chạy");
    } catch (err) {
      state.runStopRequested = false;
      syncRunButtonState();
      toast("Không dừng được ứng dụng: " + err.message, true);
    }
  }

  function switchMainTab(name, options = {}) {
    const allowed = new Set(["automation", "createProfile", "profiles", "proxyManager"]);
    const tabName = allowed.has(name) ? name : "automation";
    const previousTab = state.activeMainTab;
    if (tabName === "automation" && previousTab !== "automation") {
      setAppEditorView("home");
    }
    state.activeMainTab = tabName;
    setWorkspacePanel(false);
    if (options.persist !== false) {
      localStorage.setItem("ix_main_tab", tabName);
    }

    const titles = {
      automation: ["App Editor", "Ứng dụng và tiện ích trình duyệt"],
      createProfile: ["Tạo profile", "Tạo cấu hình IXBrowser mới"],
      profiles: ["Hồ sơ", "Tìm và quản lý profile IXBrowser"],
      proxyManager: ["Proxy", "Quản lý và gán proxy"],
    };
    els.workspaceTitle.textContent = titles[tabName][0];
    els.workspaceSubtitle.textContent = titles[tabName][1];
    document.querySelector(".studio")?.classList.toggle("is-workflow-view", tabName === "automation");

    document.querySelectorAll("[data-main-tab]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mainTab === tabName);
    });
    document.querySelectorAll(".workspace-tab").forEach((section) => {
      section.classList.toggle("active", section.id === `${tabName === "proxyManager" ? "proxy" : tabName}Workspace`);
    });
    document.querySelectorAll(".main-tab-content").forEach((section) => {
      section.classList.toggle("active", section.dataset.mainContent === tabName);
    });
    els.workspacePanelToggle.classList.toggle("is-hidden", tabName !== "automation");

    if (tabName === "profiles" && !state.ixProfiles.length) {
      refreshIxProfiles().catch((err) => toast("Load IX profiles failed: " + err.message, true));
    }
    if (tabName === "proxyManager" && !state.ixProxies.length) {
      refreshIxProxies().catch((err) => toast("Load IX proxies failed: " + err.message, true));
    }
  }

  function setWorkspacePanel(open) {
    const shouldOpen = Boolean(open) && state.activeMainTab === "automation";
    els.workspacePanel.classList.toggle("is-open", shouldOpen);
    els.appShell.classList.toggle("has-utility-panel", shouldOpen);
    els.workspaceScrim.hidden = true;
    els.workspacePanelToggle.setAttribute("aria-expanded", String(shouldOpen));
    if (shouldOpen) {
      els.workspaceTitle.textContent = "Tiện ích trình duyệt";
      els.workspaceSubtitle.textContent = "Cấu hình tiện ích dùng cho profile";
    } else {
      els.workspaceTitle.textContent = state.activeMainTab === "automation" ? "App Editor" : els.workspaceTitle.textContent;
      els.workspaceSubtitle.textContent = state.activeMainTab === "automation" ? "Ứng dụng và tiện ích trình duyệt" : els.workspaceSubtitle.textContent;
    }
    if (shouldOpen) {
      const firstInput = els.workspacePanel.querySelector("input:not([type=hidden]), textarea, button");
      if (firstInput) firstInput.focus();
    }
  }

  async function loadIxMetadata() {
    await Promise.all([api("/profiles/groups"), api("/profiles/tags")]);
    toast("Groups/tags reachable");
  }

  function formPayload(form) {
    const data = new FormData(form);
    const payload = {};
    data.forEach((value, key) => {
      const clean = String(value || "").trim();
      if (clean === "") return;
      if (/^-?\d+$/.test(clean) && ["group_id", "tag_id"].includes(key)) {
        payload[key] = Number(clean);
      } else {
        payload[key] = clean;
      }
    });
    form.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
      payload[checkbox.name] = checkbox.checked;
    });
    return payload;
  }

  async function createIxProfile() {
    const payload = formPayload(els.createProfileForm);
    if (!payload.name) {
      toast("Profile name is required", true);
      return;
    }
    const proxyMode = payload.proxy_mode || "direct";
    if (proxyMode === "direct") {
      payload.proxy_type = "direct";
      ["proxy_ip", "proxy_port", "proxy_user", "proxy_password", "proxy_check_line", "proxy_id"].forEach((key) => delete payload[key]);
    } else if (proxyMode === "custom") {
      if (!payload.proxy_ip) {
        toast("Proxy riêng cần có máy chủ hoặc địa chỉ IP.", true);
        return;
      }
      if (!payload.proxy_port) {
        toast("Proxy riêng cần có cổng kết nối.", true);
        return;
      }
      delete payload.proxy_id;
    } else if (proxyMode === "purchased_proxy") {
      if (!payload.proxy_id) {
        toast("Hãy nhập ID proxy đã mua.", true);
        return;
      }
      ["proxy_type", "proxy_ip", "proxy_port", "proxy_user", "proxy_password", "proxy_check_line"].forEach((key) => delete payload[key]);
    }
    const result = await api("/ix/profiles", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    els.createProfileResult.textContent = JSON.stringify(result, null, 2);
    toast("Profile created");
    state.ixProfilesPage = 1;
    await refreshIxProfiles();
    await loadProfilesForPicker();
  }

  async function refreshIxProfiles() {
    const page = Math.max(1, Number(state.ixProfilesPage || 1));
    const limit = clampProfilePageSize(els.profilesLimit.value || 20);
    const params = new URLSearchParams({
      page: String(page),
      limit: String(limit),
      group_id: String(Number(els.profilesGroupId.value || 0)),
      tag_id: String(Number(els.profilesTagId.value || 0)),
    });
    const keyword = String(els.profilesKeyword.value || "").trim();
    if (keyword) params.set("keyword", keyword);
    const [data, opened] = await Promise.all([
      api(`/ix/profiles?${params.toString()}`),
      api("/ix/profiles/opened").catch(() => ({ profiles: [] })),
    ]);
    state.ixProfiles = Array.isArray(data?.profiles) ? data.profiles : [];
    state.ixOpenedProfileIds = new Set(
      (Array.isArray(opened?.profiles) ? opened.profiles : [])
        .map((p) => String(p.profile_id || p.id || ""))
        .filter(Boolean)
    );
    state.ixProfilesTotal = Number(data?.total || state.ixProfiles.length || 0);
    state.ixProfilesPage = page;
    renderIxProfiles();
  }

  function changeIxProfilesPage(delta) {
    const limit = clampProfilePageSize(els.profilesLimit.value || 20);
    const totalPages = Math.max(1, Math.ceil((state.ixProfilesTotal || 0) / limit));
    state.ixProfilesPage = Math.max(1, Math.min(totalPages, state.ixProfilesPage + delta));
    refreshIxProfiles().catch((err) => toast("Reload profiles failed: " + err.message, true));
  }

  function profileTagsText(profile) {
    const tags = profile?.tags || profile?.tag || [];
    if (Array.isArray(tags)) {
      return tags.map((t) => t.title || t.name || t).join(", ");
    }
    return String(tags || "");
  }

  function profileProxyText(profile) {
    const proxy = profile?.proxy_config || profile?.proxy || profile?.proxy_info || {};
    if (!proxy || typeof proxy !== "object") return "";
    return [proxy.proxy_type, proxy.proxy_ip, proxy.proxy_port].filter(Boolean).join(":");
  }

  const NODE_ICONS = {
    Start: "▶",
    Variables: "ƒx",
    Stop: "■",
    "Open URL": "↗",
    Click: "⌖",
    "Press Key": "⌨",
    "Type Text": "T",
    HTTP: "⇄",
    "Open AI": "✦",
    "Image search": "▧",
    Screenshot: "◉",
    ARTEMIS: "📱",
    "ARTEMIS Open App": "▶",
    "ARTEMIS Install APKs": "⇩",
    "ARTEMIS Stop App": "■",
    "ARTEMIS Get UI": "▤",
    "ARTEMIS Find Element": "⌕",
    "ARTEMIS Wait Element": "◷",
    "ARTEMIS Read Text": "T",
    "ARTEMIS Tap": "⌖",
    "ARTEMIS Long Press": "⏱",
    "ARTEMIS Double Tap": "⌖",
    "ARTEMIS Swipe": "↕",
    "ARTEMIS Type Text": "T",
    "ARTEMIS Clear Text": "⌫",
    "ARTEMIS Set Clipboard": "▣",
    "ARTEMIS Key Event": "⌨",
    "ARTEMIS Screenshot": "◉",
    "Analyze Error": "⚠",
    Loop: "⟳",
    If: "◇",
  };

  const NODE_LABELS = {
    ARTEMIS: "Phone · Connect",
    "ARTEMIS Open App": "Phone · Open App",
    "ARTEMIS Install APKs": "Phone · Install APKs",
    "ARTEMIS Stop App": "Phone · Stop App",
    "ARTEMIS Get UI": "Phone · Get UI",
    "ARTEMIS Find Element": "Phone · Find Element",
    "ARTEMIS Wait Element": "Phone · Wait Element",
    "ARTEMIS Read Text": "Phone · Read Text",
    "ARTEMIS Tap": "Phone · Tap",
    "ARTEMIS Long Press": "Phone · Long Press",
    "ARTEMIS Double Tap": "Phone · Double Tap",
    "ARTEMIS Swipe": "Phone · Swipe",
    "ARTEMIS Type Text": "Phone · Type Text",
    "ARTEMIS Clear Text": "Phone · Clear Text",
    "ARTEMIS Set Clipboard": "Phone · Set Clipboard",
    "ARTEMIS Key Event": "Phone · Key Event",
    "ARTEMIS Screenshot": "Phone · Screenshot",
    "Analyze Error": "Flow · Analyze Error",
  };

  function nodeLabelEn(type) {
    const raw = String(type || "").trim();
    return NODE_LABELS[raw] || raw || "Node";
  }

  function nodeIcon(type) {
    const raw = String(type || "").trim();
    return NODE_ICONS[raw] || "·";
  }

  function paletteGroupLabel(label) {
    const labels = {
      "Start - Stop": "Luồng chạy",
      "Navigation Bar": "Điều hướng",
      "Mouse Bar": "Chuột",
      "Keyboard Bar": "Bàn phím",
      "Data Bar": "Dữ liệu và tích hợp",
      Other: "Khác",
      "ARTEMIS Phone": "Điện thoại (ARTEMIS)",
    };
    return labels[label] || label;
  }

  function renderIxProfiles() {
    const limit = clampProfilePageSize(els.profilesLimit.value || 20);
    const totalPages = Math.max(1, Math.ceil((state.ixProfilesTotal || state.ixProfiles.length) / limit));
    els.profilesPageLabel.textContent = `${state.ixProfilesPage}/${totalPages}`;
    els.profilesPrevBtn.disabled = state.ixProfilesPage <= 1;
    els.profilesNextBtn.disabled = state.ixProfilesPage >= totalPages;
    if (!state.ixProfiles.length) {
      els.profilesTable.innerHTML = "<div class='ix-empty'>Chưa có profile trên trang này. Tải lại hoặc thay đổi bộ lọc để tiếp tục.</div>";
      return;
    }
    const rows = state.ixProfiles
      .map((p) => {
        const id = String(p.profile_id || p.id || "");
        const name = p.name || "(Chưa đặt tên)";
        const opened = state.ixOpenedProfileIds.has(id);
        return `
          <tr>
            <td class="ix-row-check"><input type="checkbox" aria-label="Chọn profile ${escapeHtml(name)}" data-ix-profile-select="${escapeHtml(id)}" ${state.selectedProfileIds.includes(id) ? "checked" : ""} /></td>
            <td class="ix-profile-id">${escapeHtml(id || "—")}</td>
            <td class="ix-profile-name"><strong>${escapeHtml(name)}</strong><small>${escapeHtml(p.platform || p.platform_name || p.browser || "Profile trình duyệt")}</small></td>
            <td>${escapeHtml(profileTagsText(p) || "—")}</td>
            <td>${escapeHtml(p.note || "—")}</td>
            <td>${escapeHtml(profileProxyText(p) || "Direct")}</td>
            <td><span class="ix-status ${opened ? "opened" : ""}"><span class="status-dot"></span>${opened ? "Đang mở" : "Sẵn sàng"}</span></td>
            <td class="ix-profile-actions">
              <button class="${opened ? "secondary" : "primary"}" data-profile-action="${opened ? "close" : "open"}" data-profile-id="${escapeHtml(id)}">${opened ? "Đóng" : "Mở"}</button>
              <details class="profile-actions-menu">
                <summary aria-label="Thao tác khác cho ${escapeHtml(name)}">···</summary>
                <div class="profile-actions-popover">
                  <button type="button" data-profile-action="edit" data-profile-id="${escapeHtml(id)}">Sửa thông tin</button>
                  <button type="button" data-profile-action="copy" data-profile-id="${escapeHtml(id)}">Sao chép profile</button>
                  <button type="button" data-profile-action="random" data-profile-id="${escapeHtml(id)}">Đổi fingerprint</button>
                  <button type="button" class="is-danger" data-profile-action="delete" data-profile-id="${escapeHtml(id)}">Xóa profile</button>
                </div>
              </details>
            </td>
          </tr>
        `;
      })
      .join("");
    els.profilesTable.innerHTML = `
      <div class="ix-table-scroll">
        <table class="ix-profile-table">
          <thead><tr><th aria-label="Chọn"></th><th>ID</th><th>Tên</th><th>Thẻ</th><th>Ghi chú</th><th>Proxy</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
    els.profilesTable.querySelectorAll("[data-profile-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        handleProfileAction(btn.dataset.profileAction, btn.dataset.profileId).catch((err) =>
          toast("Profile action failed: " + err.message, true)
        );
      });
    });
    els.profilesTable.querySelectorAll("[data-ix-profile-select]").forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        toggleProfileSelection(checkbox.dataset.ixProfileSelect, checkbox.checked);
        syncSelectedProfilesToInput();
      });
    });
  }

  async function handleProfileAction(action, profileId) {
    if (!profileId) return;
    if (action === "delete") {
      const typed = prompt(`Type profile id ${profileId} to delete`);
      if (typed !== profileId) return;
      await api(`/ix/profiles/${encodeURIComponent(profileId)}`, { method: "DELETE" });
      toast("Profile deleted");
    } else if (action === "open") {
      await api(`/ix/profiles/${encodeURIComponent(profileId)}/open`, { method: "POST" });
      toast("Profile opened");
    } else if (action === "close") {
      await api(`/ix/profiles/${encodeURIComponent(profileId)}/close`, { method: "POST" });
      toast("Profile closed");
    } else if (action === "edit") {
      const profile = state.ixProfiles.find((p) => String(p.profile_id || p.id || "") === String(profileId)) || {};
      const raw = prompt(
        "Edit profile JSON fields",
        JSON.stringify(
          {
            name: profile.name || "",
            group_id: profile.group_id || 0,
            tag: profileTagsText(profile),
            note: profile.note || "",
          },
          null,
          2
        )
      );
      if (!raw) return;
      await api(`/ix/profiles/${encodeURIComponent(profileId)}`, {
        method: "PUT",
        body: JSON.stringify(JSON.parse(raw)),
      });
      toast("Profile updated");
    } else if (action === "copy") {
      const name = prompt("Copy profile name", `Copy of ${profileId}`) || "";
      await api(`/ix/profiles/${encodeURIComponent(profileId)}/copy`, {
        method: "POST",
        body: JSON.stringify(name ? { name } : {}),
      });
      toast("Profile copied");
    } else if (action === "random") {
      await api(`/ix/profiles/${encodeURIComponent(profileId)}/random-fingerprint`, { method: "POST" });
      toast("Fingerprint randomized");
    }
    await refreshIxProfiles();
    await loadProfilesForPicker();
  }

  async function refreshIxProxies() {
    const page = Math.max(1, Number(state.ixProxiesPage || 1));
    const limit = clampProfilePageSize(els.proxiesLimit.value || 20);
    const params = new URLSearchParams({
      page: String(page),
      limit: String(limit),
      mode: String(Number(els.proxiesMode.value || 0)),
      tag_id: String(Number(els.proxiesTagId.value || 0)),
    });
    const data = await api(`/ix/proxies?${params.toString()}`);
    state.ixProxies = Array.isArray(data?.proxies) ? data.proxies : [];
    state.ixProxiesTotal = Number(data?.total || state.ixProxies.length || 0);
    state.ixProxiesPage = page;
    renderIxProxies();
  }

  function changeIxProxiesPage(delta) {
    const limit = clampProfilePageSize(els.proxiesLimit.value || 20);
    const totalPages = Math.max(1, Math.ceil((state.ixProxiesTotal || 0) / limit));
    state.ixProxiesPage = Math.max(1, Math.min(totalPages, state.ixProxiesPage + delta));
    refreshIxProxies().catch((err) => toast("Reload proxies failed: " + err.message, true));
  }

  function renderIxProxies() {
    const query = String(els.proxiesSearch.value || "").trim().toLowerCase();
    const visible = state.ixProxies.filter((p) => {
      if (!query) return true;
      return `${p.proxy_ip || ""} ${p.note || ""} ${p.proxy_user || ""} ${p.tag || ""}`.toLowerCase().includes(query);
    });
    const limit = clampProfilePageSize(els.proxiesLimit.value || 20);
    const totalPages = Math.max(1, Math.ceil((state.ixProxiesTotal || state.ixProxies.length) / limit));
    els.proxiesPageLabel.textContent = `${state.ixProxiesPage}/${totalPages}`;
    els.proxiesPrevBtn.disabled = state.ixProxiesPage <= 1;
    els.proxiesNextBtn.disabled = state.ixProxiesPage >= totalPages;
    if (!visible.length) {
      els.proxiesTable.innerHTML = "<div class='ix-empty'>Chưa có proxy phù hợp.</div>";
      return;
    }
    els.proxiesTable.innerHTML = visible
      .map((p) => {
        const id = String(p.id || p.proxy_id || "");
        const endpoint = [p.proxy_type, p.proxy_ip, p.proxy_port].filter(Boolean).join(":");
        return `
          <div class="ix-row ${state.ixSelectedProxy && String(state.ixSelectedProxy.id || state.ixSelectedProxy.proxy_id) === id ? "active" : ""}">
            <div class="ix-row-main">
              <strong>${escapeHtml(endpoint || `Proxy ${id}`)}</strong>
              <small>ID ${escapeHtml(id)} | thẻ ${escapeHtml(p.tag || "-")} | ghi chú ${escapeHtml(p.note || "-")}</small>
            </div>
            <div class="ix-row-actions">
              <button class="secondary" data-proxy-action="edit" data-proxy-id="${escapeHtml(id)}">Sửa</button>
              <button class="ghost" data-proxy-action="select" data-proxy-id="${escapeHtml(id)}">Chọn</button>
              <button class="danger" data-proxy-action="delete" data-proxy-id="${escapeHtml(id)}">Xóa</button>
            </div>
          </div>
        `;
      })
      .join("");
    els.proxiesTable.querySelectorAll("[data-proxy-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        handleProxyAction(btn.dataset.proxyAction, btn.dataset.proxyId).catch((err) =>
          toast("Proxy action failed: " + err.message, true)
        );
      });
    });
  }

  function proxyById(proxyId) {
    return state.ixProxies.find((p) => String(p.id || p.proxy_id || "") === String(proxyId));
  }

  function fillProxyForm(proxy) {
    const form = els.proxyForm;
    form.elements.proxy_id.value = proxy ? String(proxy.id || proxy.proxy_id || "") : "";
    form.elements.proxy_type.value = proxy?.proxy_type || "http";
    form.elements.proxy_ip.value = proxy?.proxy_ip || "";
    form.elements.proxy_port.value = proxy?.proxy_port || "";
    form.elements.proxy_user.value = proxy?.proxy_user || "";
    form.elements.proxy_password.value = proxy?.proxy_password || "";
    form.elements.note.value = proxy?.note || "";
    form.elements.tag.value = proxy?.tag || "";
  }

  function resetProxyForm() {
    state.ixSelectedProxy = null;
    fillProxyForm(null);
    renderIxProxies();
  }

  async function handleProxyAction(action, proxyId) {
    const proxy = proxyById(proxyId);
    if (!proxy) return;
    if (action === "delete") {
      if (!confirm(`Delete proxy ${proxyId}?`)) return;
      try {
        await api(`/ix/proxies/${encodeURIComponent(proxyId)}`, { method: "DELETE" });
      } catch (err) {
        if (!isProxyInUseError(err)) throw err;
        const using = await api(`/ix/proxies/${encodeURIComponent(proxyId)}/profiles`);
        const count = Number(using?.count || 0);
        const sample = (Array.isArray(using?.profiles) ? using.profiles : [])
          .slice(0, 5)
          .map((profile) => `${profile.name || "(no name)"} #${profile.profile_id || profile.id}`)
          .join("\n");
        const message =
          `Proxy ${proxyId} đang được dùng bởi ${count} profile.\n\n` +
          `${sample ? sample + "\n\n" : ""}` +
          "Gỡ proxy khỏi các profile này về DIRECT rồi xoá proxy?";
        if (!confirm(message)) {
          toast("Proxy is still assigned to profiles. Delete cancelled.", true);
          return;
        }
        await api(`/ix/proxies/${encodeURIComponent(proxyId)}?detach_profiles=true`, {
          method: "DELETE",
        });
      }
      toast("Proxy deleted");
      await refreshIxProxies();
      await refreshIxProfiles();
      return;
    }
    state.ixSelectedProxy = proxy;
    fillProxyForm(proxy);
    renderIxProxies();
  }

  async function saveIxProxy() {
    const payload = formPayload(els.proxyForm);
    const proxyId = String(payload.proxy_id || "").trim();
    delete payload.proxy_id;
    const path = proxyId ? `/ix/proxies/${encodeURIComponent(proxyId)}` : "/ix/proxies";
    const method = proxyId ? "PUT" : "POST";
    await api(path, { method, body: JSON.stringify(payload) });
    toast(proxyId ? "Proxy updated" : "Proxy created");
    resetProxyForm();
    await refreshIxProxies();
  }

  function isProxyInUseError(err) {
    const message = String(err?.message || err || "").toLowerCase();
    return message.includes("108002") || message.includes("still in use") || message.includes("in a profile");
  }

  async function assignProxyToSelectedProfiles() {
    const proxy = state.ixSelectedProxy;
    if (!proxy) {
      toast("Select a proxy first", true);
      return;
    }
    if (!state.selectedProfileIds.length) {
      toast("Select profiles first", true);
      return;
    }
    const proxyId = String(proxy.id || proxy.proxy_id || "");
    const isPurchased = Number(proxy.type || proxy.mode || proxy.proxy_mode || 0) === 2;
    const calls = state.selectedProfileIds.map((profileId) => {
      if (isPurchased && proxyId) {
        return api(`/ix/profiles/${encodeURIComponent(profileId)}/proxy/purchased`, {
          method: "PUT",
          body: JSON.stringify({ proxy_id: proxyId }),
        });
      }
      return api(`/ix/profiles/${encodeURIComponent(profileId)}/proxy/custom`, {
        method: "PUT",
        body: JSON.stringify({
          proxy_type: proxy.proxy_type || "http",
          proxy_ip: proxy.proxy_ip,
          proxy_port: proxy.proxy_port,
          proxy_user: proxy.proxy_user,
          proxy_password: proxy.proxy_password,
          proxy_check_line: "global_line",
        }),
      });
    });
    await Promise.all(calls);
    toast(`Assigned proxy to ${state.selectedProfileIds.length} profiles`);
    await refreshIxProfiles();
  }

  function switchTab(name) {
    const targetId = `${name}Tab`;
    const hasTarget = Array.from(document.querySelectorAll(".tab-body")).some(
      (body) => body.id === targetId
    );
    const finalName = hasTarget ? name : "builder";
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.tab === finalName);
    });
    document.querySelectorAll(".tab-body").forEach((body) => {
      body.classList.toggle("active", body.id === `${finalName}Tab`);
    });
  }

  function exportGraph() {
    const payload = {
      app_id: state.currentAppId,
      name: els.appName.value.trim(),
      description: els.appDesc.value.trim(),
      graph: { nodes: state.nodes, edges: state.edges, inputs: state.inputs },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(payload.name || "automation_app").replace(/\s+/g, "_").toLowerCase()}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function exportAppBundle() {
    if (!state.currentAppId) { toast("Lưu ứng dụng trước khi đóng gói.", true); return; }
    const headers = state.token ? { Authorization: `Bearer ${state.token}` } : {};
    const response = await fetch(`/automation/apps/${encodeURIComponent(state.currentAppId)}/bundle`, { headers });
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`;
      try { const payload = await response.json(); message = payload.detail || message; } catch (_) {}
      throw new Error(message);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `${(els.appName.value.trim() || "autoixb-app").replace(/[^\w-]+/g, "_")}.zip`;
    document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
    toast("Đã đóng gói app cha, app con và ảnh mẫu.");
  }

  async function importAppBundle() {
    const fileInput = byId("importBundleFile"); const file = fileInput.files?.[0];
    if (!file) return;
    const body = new FormData(); body.append("file", file, file.name);
    const result = await api("/automation/apps/import-bundle", { method: "POST", body });
    fileInput.value = "";
    await refreshApps();
    await selectApp(result.root.id);
    toast(`Đã nhập ${result.apps.length} app và ${result.asset_count} ảnh mẫu.`);
  }

  function shortConfig(config) {
    const keys = Object.keys(config || {});
    if (!keys.length) return "Chưa có cấu hình";
    const preview = keys
      .slice(0, 2)
      .map((k) => `${k}:${String(config[k]).slice(0, 12)}`)
      .join(" | ");
    return preview + (keys.length > 2 ? " ..." : "");
  }

  function parseSmartValue(raw) {
    if (raw === "") return "";
    if (raw === "true") return true;
    if (raw === "false") return false;
    if (/^-?\d+(\.\d+)?$/.test(raw)) return Number(raw);
    if ((raw.startsWith("{") && raw.endsWith("}")) || (raw.startsWith("[") && raw.endsWith("]"))) {
      try {
        return JSON.parse(raw);
      } catch (_) {
        return raw;
      }
    }
    return raw;
  }

  function timeAgo(ts) {
    if (!ts) return "";
    const diff = Math.max(0, Date.now() / 1000 - ts);
    if (diff < 60) return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  function isPlainObject(value) {
    return Object.prototype.toString.call(value) === "[object Object]";
  }

  function toast(message, isError) {
    els.toast.textContent = message;
    els.toast.style.background = isError ? "#6b1f1f" : "#1f2c38";
    els.toast.classList.add("show");
    setTimeout(() => els.toast.classList.remove("show"), 2200);
  }

  function byId(id) {
    const el = document.getElementById(id);
    if (!el) throw new Error(`Missing element #${id}`);
    return el;
  }

  function uniqueId(prefix) {
    return `${prefix}_${Math.random().toString(36).slice(2, 8)}`;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
})();

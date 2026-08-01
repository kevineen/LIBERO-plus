// VR teleop thin client for Meta Quest 3 (OpenXR).
// Requires NativeWebSocket: https://github.com/endel/NativeWebSocket
using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
#if UNITY_INPUT_SYSTEM
using UnityEngine.InputSystem;
using UnityEngine.XR.OpenXR.Input;
#endif

#if NATIVE_WEBSOCKET
using NativeWebSocket;
#endif

/// <summary>
/// Quest → parc-vr-teleop WebSocket クライアント。
/// 右手コントローラ姿勢・グリッパ・録画ボタンを送り、JPEG をパネルに貼る。
/// </summary>
public class VrTeleopClient : MonoBehaviour
{
    [Header("Connection")]
    [Tooltip("例: ws://192.168.11.5:8765")]
    public string serverUrl = "ws://127.0.0.1:8765";

    [Header("XR")]
    public Transform rightController;
    [Range(0f, 1f)] public float gripper;
    public bool buttonRecord;
    public bool buttonSave;
    public bool buttonDiscard;
    public bool buttonReset;

    [Header("Video panels")]
    public Renderer frontPanel;
    public Renderer wristPanel;

    [Header("Tuning")]
    public float sendHz = 20f;

    [Header("Debug")]
    [Tooltip("Editor で最初の JPEG を PNG 保存（映像確認用）")]
    public bool saveFirstFramesInEditor = true;
    [Tooltip("FrontPanel 異常（材質剥がれ・wrist 混入など）を Console に出す")]
    public bool debugFrontPanel = true;
    [Tooltip("異常検知時に PNG を保存（Editor のみ）")]
    public bool saveFrontAnomalyPng = true;

    private float _sendPeriod;
    private float _sendAcc;
    private Texture2D _frontTex;
    private Texture2D _wristTex;
    private string _language = "";
    private bool _recording;
    private int _jpegOkCount;
    private bool _savedFront;
    private bool _savedWrist;
    private Material _frontMatInstance;
    private Material _wristMatInstance;
    private bool _warnedSamePanel;
    private bool _frontBound;
    private bool _wristBound;
    // 最新フレームのみ描画（キュー溜まりで一気に Apply するとたまにカクつく）
    private byte[] _pendingFrontRgb = Array.Empty<byte>();
    private byte[] _pendingWristRgb = Array.Empty<byte>();
    private int _pendingFrontW;
    private int _pendingFrontH;
    private int _pendingWristW;
    private int _pendingWristH;
    private bool _frontDirty;
    private bool _wristDirty;
    private int _droppedFrames;
    private byte[] _frontRgba = Array.Empty<byte>();
    private byte[] _wristRgba = Array.Empty<byte>();
    private uint _lastFrontChecksum;
    private uint _lastWristChecksum;
    private bool _haveFrontChecksum;
    private bool _haveWristChecksum;
    private int _frontAnomalyCount;
    private int _frontMatRepairCount;
    private float _nextFrontOkLog;

#if NATIVE_WEBSOCKET
    private WebSocket _ws;
#endif

    private void Awake()
    {
        _sendPeriod = 1f / Mathf.Max(1f, sendHz);
        // パネルごとに独立した Texture（RGB24 は GPU により不安定 → RGBA32）
        _frontTex = new Texture2D(2, 2, TextureFormat.RGBA32, false);
        _wristTex = new Texture2D(2, 2, TextureFormat.RGBA32, false);
        _frontTex.name = "VrTeleopFrontTex";
        _wristTex.name = "VrTeleopWristTex";
        _frontTex.wrapMode = TextureWrapMode.Clamp;
        _wristTex.wrapMode = TextureWrapMode.Clamp;
        _frontTex.filterMode = FilterMode.Bilinear;
        _wristTex.filterMode = FilterMode.Bilinear;
        // Editor でオブジェクト選択時にランタイム資産がシリアライズ／巻き戻されないようにする
        _frontTex.hideFlags = HideFlags.HideAndDontSave;
        _wristTex.hideFlags = HideFlags.HideAndDontSave;
        // Editor / パネル確認用: Right Controller 未割当でも control を送れるようにする
        if (rightController == null)
        {
            var go = new GameObject("RightControllerAnchor_auto");
            go.transform.SetParent(transform, false);
            rightController = go.transform;
        }
    }

    private async void Start()
    {
        // この行が出なければ Unity が古い Assembly-CSharp.dll を使っている（要 Reimport）
        Debug.Log("[VrTeleop] client build: front-diag (2026-08-01j)");
        if (frontPanel != null && wristPanel != null && ReferenceEquals(frontPanel, wristPanel))
        {
            Debug.LogError(
                "[VrTeleop] Front Panel と Wrist Panel が同じ Renderer です。" +
                "Inspector で別々の Renderer を割り当ててください（映像が交互にチラつきます）。"
            );
        }
        WarnIfPanelParentedToCamera(frontPanel, "FrontPanel");
        WarnIfPanelParentedToCamera(wristPanel, "WristPanel");
        EnsureUniquePanelMaterials();
#if NATIVE_WEBSOCKET
        _ws = new WebSocket(serverUrl);
        _ws.OnOpen += () => Debug.Log($"[VrTeleop] connected {serverUrl}");
        _ws.OnError += (e) => Debug.LogError($"[VrTeleop] {e}");
        _ws.OnClose += (c) => Debug.Log($"[VrTeleop] closed {c}");
        _ws.OnMessage += OnMessage;
        await _ws.Connect();
#else
        Debug.LogWarning(
            "[VrTeleop] Define NATIVE_WEBSOCKET and import NativeWebSocket package. " +
            "See unity/VrTeleop/README.md"
        );
#endif
    }

    /// <summary>
    /// パネルが Camera の子孫だと Stereo で左右ずれ・二重像になる。
    /// </summary>
    private static void WarnIfPanelParentedToCamera(Renderer panel, string label)
    {
        if (panel == null)
        {
            return;
        }
        Transform t = panel.transform;
        while (t != null)
        {
            if (t.GetComponent<Camera>() != null)
            {
                Debug.LogError(
                    $"[VrTeleop] {label} が Camera「{t.name}」の子です。" +
                    "Stereo で左右ずれ／二重像になります。" +
                    "VrTeleopHudFollow 配下（Camera の外）に移してください。"
                );
                return;
            }
            t = t.parent;
        }
    }

    /// <summary>
    /// Front/Wrist それぞれに Unlit の新規 Material を割り当てる（シーン資産を汚さない）。
    /// </summary>
    private void EnsureUniquePanelMaterials()
    {
        Shader shader = Shader.Find("Unlit/Texture");
        if (shader == null)
        {
            shader = Shader.Find("UI/Default");
        }
        if (frontPanel != null && _frontMatInstance == null)
        {
            _frontMatInstance = new Material(shader)
            {
                name = "VrTeleopFrontMat_runtime",
                hideFlags = HideFlags.HideAndDontSave,
                mainTexture = _frontTex,
            };
            _frontMatInstance.enableInstancing = false;
            frontPanel.SetPropertyBlock(null);
            frontPanel.sharedMaterial = _frontMatInstance;
        }
        if (wristPanel != null && _wristMatInstance == null)
        {
            _wristMatInstance = new Material(shader)
            {
                name = "VrTeleopWristMat_runtime",
                hideFlags = HideFlags.HideAndDontSave,
                mainTexture = _wristTex,
            };
            _wristMatInstance.enableInstancing = false;
            wristPanel.SetPropertyBlock(null);
            wristPanel.sharedMaterial = _wristMatInstance;
        }
        if (_frontMatInstance != null && _wristMatInstance != null
            && ReferenceEquals(_frontMatInstance, _wristMatInstance))
        {
            Debug.LogError("[VrTeleop] runtime materials are unexpectedly shared");
        }
    }

    private void Update()
    {
#if NATIVE_WEBSOCKET
        _ws?.DispatchMessageQueue();
#endif
        // Dispatch で溜まった中間フレームは捨て、最新だけ GPU に載せる
        FlushPendingRgb();
        SampleDebugButtons();
        _sendAcc += Time.deltaTime;
        if (_sendAcc < _sendPeriod)
        {
            return;
        }
        _sendAcc = 0f;
        SendControl();
    }

    private async void OnDestroy()
    {
#if NATIVE_WEBSOCKET
        if (_ws != null)
        {
            await _ws.Close();
        }
#endif
    }

    /// <summary>
    /// Editor / デバッグ用キーボード。
    /// 実機の XR は <see cref="VrTeleopXrBinder"/> が担当。
    /// キー押下中だけ上書き（離したら XR 側の値に戻る）。
    /// </summary>
    private void SampleDebugButtons()
    {
#if UNITY_EDITOR
        // Inspector / Console 入力中にキーを拾うと EE が飛び映像も乱れる
        if (UnityEditor.EditorGUIUtility.editingTextField)
        {
            return;
        }
        if (!Application.isFocused)
        {
            return;
        }
#endif
        bool any =
            Input.GetKey(KeyCode.R)
            || Input.GetKey(KeyCode.S)
            || Input.GetKey(KeyCode.G)
            || Input.GetKey(KeyCode.T)
            || Input.GetKey(KeyCode.Backspace);
        if (any)
        {
            buttonRecord = Input.GetKey(KeyCode.R);
            buttonSave = Input.GetKey(KeyCode.S);
            buttonDiscard = Input.GetKey(KeyCode.G);
            buttonReset = Input.GetKey(KeyCode.T) || Input.GetKey(KeyCode.Backspace);
        }
        // 矢印で EE を動かす（Editor で操作確認）
        if (rightController != null)
        {
            Vector3 d = Vector3.zero;
            if (Input.GetKey(KeyCode.UpArrow))
            {
                d.z += 0.01f;
            }
            if (Input.GetKey(KeyCode.DownArrow))
            {
                d.z -= 0.01f;
            }
            if (Input.GetKey(KeyCode.LeftArrow))
            {
                d.x -= 0.01f;
            }
            if (Input.GetKey(KeyCode.RightArrow))
            {
                d.x += 0.01f;
            }
            if (Input.GetKey(KeyCode.PageUp))
            {
                d.y += 0.01f;
            }
            if (Input.GetKey(KeyCode.PageDown))
            {
                d.y -= 0.01f;
            }
            if (d.sqrMagnitude > 0f)
            {
                rightController.position += d;
            }
        }
    }

    private void SendControl()
    {
        // rightController 未割当でも control を送り続ける。
        // 送らないとサーバが step/映像更新せず、fake の初期黒フレームのままになる。
        Vector3 p = rightController != null ? rightController.position : Vector3.zero;
        Quaternion q = rightController != null ? rightController.rotation : Quaternion.identity;
        // Unity は (x,y,z,w)
        string json =
            "{"
            + "\"type\":\"control\","
            + $"\"t\":{Time.realtimeSinceStartup.ToString(System.Globalization.CultureInfo.InvariantCulture)},"
            + "\"pose\":{"
            + $"\"pos\":[{F(p.x)},{F(p.y)},{F(p.z)}],"
            + $"\"quat\":[{F(q.x)},{F(q.y)},{F(q.z)},{F(q.w)}]"
            + "},"
            + $"\"gripper\":{F(Mathf.Clamp01(gripper))},"
            + "\"buttons\":{"
            + $"\"record\":{(buttonRecord ? "true" : "false")},"
            + $"\"save\":{(buttonSave ? "true" : "false")},"
            + $"\"discard\":{(buttonDiscard ? "true" : "false")},"
            + $"\"reset\":{(buttonReset ? "true" : "false")}"
            + "}}";

#if NATIVE_WEBSOCKET
        if (_ws != null && _ws.State == WebSocketState.Open)
        {
            _ = _ws.SendText(json);
        }
#endif
        // エッジはクライアント側で維持しない（サーバが rising edge 検出）
        // 物理ボタンを離したら Inspector / Input 側で false に戻す想定
    }

    private void OnMessage(byte[] bytes)
    {
        if (bytes == null || bytes.Length == 0)
        {
            return;
        }

        // Binary: 0x01/0x02 = JPEG, 0x11/0x12 = RGB24 + size header
        if (bytes[0] == 0x01 || bytes[0] == 0x02)
        {
            ApplyJpeg(bytes[0], bytes, 1);
            return;
        }
        if (bytes[0] == 0x11 || bytes[0] == 0x12)
        {
            // 即 Apply せず最新だけ保持（1 Update に数十枚来るとチラつく）
            QueueRgb(bytes[0], bytes);
            return;
        }
        // 制御文字っぽい先頭は旧クライアント未対応のバイナリの可能性
        if (bytes[0] < 0x20)
        {
            Debug.LogWarning(
                $"[VrTeleop] unknown binary head=0x{bytes[0]:X2} len={bytes.Length} — " +
                "Assets→Reimport All で最新 VrTeleopClient を再コンパイルしてください"
            );
            return;
        }

        string text = Encoding.UTF8.GetString(bytes);
        HandleJson(text);
    }

    private void HandleJson(string text)
    {
        // 最小パース（JsonUtility 用ラッパがネストに弱いため手で拾う）
        if (text.Contains("\"task_info\""))
        {
            _language = ExtractString(text, "language");
            Debug.Log($"[VrTeleop] task language: {_language}");
        }
        if (text.Contains("\"status\""))
        {
            _recording = text.Contains("\"recording\": true") || text.Contains("\"recording\":true");
        }
        if (text.Contains("\"episode_saved\""))
        {
            Debug.Log("[VrTeleop] episode saved");
        }
        if (text.Contains("\"error\""))
        {
            Debug.LogError($"[VrTeleop] server error: {text}");
        }
    }

    /// <summary>
    /// RGB を pending にコピー。未 Flush の古いフレームは捨てる。
    /// </summary>
    private void QueueRgb(byte cameraId, byte[] buffer)
    {
        // [id][w_lo][w_hi][h_lo][h_hi][rgb...]
        if (buffer.Length < 5)
        {
            Debug.LogWarning($"[VrTeleop] rgb frame too short len={buffer.Length}");
            return;
        }
        int w = buffer[1] | (buffer[2] << 8);
        int h = buffer[3] | (buffer[4] << 8);
        int expect = w * h * 3;
        if (w <= 0 || h <= 0 || buffer.Length != 5 + expect)
        {
            Debug.LogWarning(
                $"[VrTeleop] rgb size mismatch w={w} h={h} len={buffer.Length} expect={5 + expect}"
            );
            return;
        }

        bool isFront = cameraId == 0x11;
        if (isFront)
        {
            if (_frontDirty)
            {
                _droppedFrames++;
            }
            EnsureCapacity(ref _pendingFrontRgb, expect);
            Buffer.BlockCopy(buffer, 5, _pendingFrontRgb, 0, expect);
            _pendingFrontW = w;
            _pendingFrontH = h;
            _frontDirty = true;
        }
        else
        {
            if (_wristDirty)
            {
                _droppedFrames++;
            }
            EnsureCapacity(ref _pendingWristRgb, expect);
            Buffer.BlockCopy(buffer, 5, _pendingWristRgb, 0, expect);
            _pendingWristW = w;
            _pendingWristH = h;
            _wristDirty = true;
        }
    }

    private void FlushPendingRgb()
    {
        if (_frontDirty)
        {
            _frontDirty = false;
            ApplyRgbBuffer(
                isFront: true,
                _pendingFrontRgb,
                _pendingFrontW,
                _pendingFrontH
            );
        }
        if (_wristDirty)
        {
            _wristDirty = false;
            ApplyRgbBuffer(
                isFront: false,
                _pendingWristRgb,
                _pendingWristW,
                _pendingWristH
            );
        }
        if (debugFrontPanel)
        {
            DiagnoseFrontPanel();
        }
    }

    /// <summary>
    /// FrontPanel の Material / Texture / 内容が期待どおりか検査してログする。
    /// Console フィルタ: <c>[VrTeleop][FrontDiag]</c>
    /// </summary>
    private void DiagnoseFrontPanel()
    {
        if (frontPanel == null || _frontTex == null)
        {
            return;
        }

        bool anomaly = false;
        var sb = new StringBuilder(256);

        Material bound = frontPanel.sharedMaterial;
        if (_frontMatInstance != null && !ReferenceEquals(bound, _frontMatInstance))
        {
            anomaly = true;
            sb.Append($" matMismatch got={(bound != null ? bound.name : "null")}");
            sb.Append($" expect={_frontMatInstance.name}");
        }

        Texture texOnMat = bound != null ? bound.mainTexture : null;
        if (_frontTex != null && !ReferenceEquals(texOnMat, _frontTex))
        {
            anomaly = true;
            sb.Append($" texMismatch got={(texOnMat != null ? texOnMat.name : "null")}");
            sb.Append($" expect={_frontTex.name}");
        }

        // wrist 映像が front に入っていないか（同一チェックサム）
        // 起動直後の黒フレームは除外
        if (_jpegOkCount > 30
            && _haveFrontChecksum && _haveWristChecksum
            && _lastFrontChecksum == _lastWristChecksum
            && _lastFrontChecksum != 0)
        {
            anomaly = true;
            sb.Append($" sameChecksumAsWrist=0x{_lastFrontChecksum:X8}");
        }

        // wrist の Material が front Renderer に載っていないか
        if (_wristMatInstance != null && ReferenceEquals(bound, _wristMatInstance))
        {
            anomaly = true;
            sb.Append(" wristMatOnFrontRenderer");
        }

        if (wristPanel != null && ReferenceEquals(frontPanel, wristPanel))
        {
            anomaly = true;
            sb.Append(" sameRendererAsWrist");
        }

        if (anomaly)
        {
            _frontAnomalyCount++;
            Debug.LogWarning(
                $"[VrTeleop][FrontDiag] ANOMALY#{_frontAnomalyCount} n={_jpegOkCount} " +
                $"frontCk=0x{_lastFrontChecksum:X8} wristCk=0x{_lastWristChecksum:X8} " +
                $"repairs={_frontMatRepairCount}{sb}"
            );
#if UNITY_EDITOR
            if (saveFrontAnomalyPng && _frontAnomalyCount <= 5)
            {
                SavePng(_frontTex, $"vr_teleop_front_anom_{_frontAnomalyCount}.png");
                if (_wristTex != null)
                {
                    SavePng(_wristTex, $"vr_teleop_wrist_anom_{_frontAnomalyCount}.png");
                }
            }
#endif
            // 異常時は強制リバインド
            BindPanel(frontPanel, _frontTex, isFront: true);
            return;
        }

        // 正常時は低頻度で状態を出す（フィルタ用）
        if (Time.unscaledTime >= _nextFrontOkLog)
        {
            _nextFrontOkLog = Time.unscaledTime + 5f;
            Debug.Log(
                $"[VrTeleop][FrontDiag] ok n={_jpegOkCount} " +
                $"frontCk=0x{_lastFrontChecksum:X8} wristCk=0x{_lastWristChecksum:X8} " +
                $"mat={(_frontMatInstance != null ? _frontMatInstance.name : "null")} " +
                $"tex={_frontTex.width}x{_frontTex.height} anomalies={_frontAnomalyCount} repairs={_frontMatRepairCount}"
            );
        }
    }

    /// <summary>RGB バッファの簡易チェックサム（混線検知用）。</summary>
    private static uint ChecksumRgb(byte[] rgb, int length)
    {
        if (rgb == null || length <= 0)
        {
            return 0;
        }
        int n = Math.Min(length, rgb.Length);
        uint h = 2166136261u;
        int step = Math.Max(1, n / 2048);
        for (int i = 0; i < n; i += step)
        {
            h ^= rgb[i];
            h *= 16777619u;
        }
        // 四隅と中央付近も必ず混ぜる
        h ^= rgb[0];
        h *= 16777619u;
        h ^= rgb[n - 1];
        h *= 16777619u;
        if (n > 3)
        {
            h ^= rgb[n / 2];
            h *= 16777619u;
        }
        return h;
    }

    private void ApplyRgbBuffer(bool isFront, byte[] rgb, int w, int h)
    {
        int expectRgb = w * h * 3;
        if (rgb == null || rgb.Length < expectRgb)
        {
            return;
        }

        Texture2D target = isFront ? _frontTex : _wristTex;
        if (target.width != w || target.height != h || target.format != TextureFormat.RGBA32)
        {
            target.Reinitialize(w, h, TextureFormat.RGBA32, false);
            target.filterMode = FilterMode.Bilinear;
            target.wrapMode = TextureWrapMode.Clamp;
            target.hideFlags = HideFlags.HideAndDontSave;
        }

        // RGB24 直載せは環境によって色ずれ／横ずれが出るため RGBA32 に展開して SetPixelData
        int expectRgba = w * h * 4;
        if (isFront)
        {
            EnsureCapacity(ref _frontRgba, expectRgba);
        }
        else
        {
            EnsureCapacity(ref _wristRgba, expectRgba);
        }
        byte[] rgba = isFront ? _frontRgba : _wristRgba;
        int si = 0;
        int di = 0;
        int pixels = w * h;
        for (int i = 0; i < pixels; i++)
        {
            rgba[di++] = rgb[si++];
            rgba[di++] = rgb[si++];
            rgba[di++] = rgb[si++];
            rgba[di++] = 255;
        }
        target.SetPixelData(rgba, 0);
        target.Apply(false, false);

        // 診断用チェックサム（アップロード前の RGB）
        uint ck = ChecksumRgb(rgb, expectRgb);
        if (isFront)
        {
            _lastFrontChecksum = ck;
            _haveFrontChecksum = true;
        }
        else
        {
            _lastWristChecksum = ck;
            _haveWristChecksum = true;
        }

        _jpegOkCount++;
        if (_jpegOkCount <= 4 || (_jpegOkCount % 60) == 0)
        {
            Debug.Log(
                $"[VrTeleop] rgb ok cam={(isFront ? 0x11 : 0x12):X2} {w}x{h} n={_jpegOkCount} drop={_droppedFrames} ck=0x{ck:X8}"
            );
        }
#if UNITY_EDITOR
        if (saveFirstFramesInEditor)
        {
            if (isFront && !_savedFront)
            {
                _savedFront = true;
                SavePng(target, "vr_teleop_front.png");
            }
            if (!isFront && !_savedWrist)
            {
                _savedWrist = true;
                SavePng(target, "vr_teleop_wrist.png");
            }
        }
#endif
        BindPanel(isFront ? frontPanel : wristPanel, target, isFront);
        if (isFront)
        {
            _frontBound = true;
        }
        else
        {
            _wristBound = true;
        }
    }

    private static void EnsureCapacity(ref byte[] buf, int size)
    {
        if (buf == null || buf.Length != size)
        {
            // LoadRawTextureData は Length == w*h*3 必須
            buf = new byte[size];
        }
    }

    private void ApplyJpeg(byte cameraId, byte[] buffer, int offset)
    {
        int len = buffer.Length - offset;
        if (len < 2)
        {
            return;
        }
        byte[] jpeg = new byte[len];
        Buffer.BlockCopy(buffer, offset, jpeg, 0, len);
#if UNITY_EDITOR
        // デコード前に生 JPEG を必ず残す（ノイズ切り分け用）
        if (saveFirstFramesInEditor && cameraId == 0x01 && !_savedFront)
        {
            try
            {
                string rawPath = System.IO.Path.Combine(Application.dataPath, "..", "vr_teleop_front.jpg");
                System.IO.File.WriteAllBytes(rawPath, jpeg);
                Debug.Log($"[VrTeleop] wrote raw jpeg {rawPath} bytes={jpeg.Length}");
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[VrTeleop] raw jpeg save failed: {e.Message}");
            }
        }
#endif
        Texture2D target = cameraId == 0x01 ? _frontTex : _wristTex;
        // JPEG SOI が無ければプロトコル／破損
        if (jpeg[0] != 0xff || jpeg[1] != 0xd8)
        {
            Debug.LogWarning(
                $"[VrTeleop] not JPEG SOI cam={cameraId} len={len} head={jpeg[0]:X2}{jpeg[1]:X2}"
            );
            return;
        }
        if (!target.LoadImage(jpeg))
        {
            Debug.LogWarning($"[VrTeleop] LoadImage failed cam={cameraId} bytes={len}");
            return;
        }
        _jpegOkCount++;
        if (_jpegOkCount <= 4 || (_jpegOkCount % 60) == 0)
        {
            Debug.Log(
                $"[VrTeleop] jpeg ok cam={cameraId} bytes={len} tex={target.width}x{target.height} n={_jpegOkCount}"
            );
        }
#if UNITY_EDITOR
        if (saveFirstFramesInEditor)
        {
            if (cameraId == 0x01 && !_savedFront)
            {
                _savedFront = true;
                SavePng(target, "vr_teleop_front.png");
            }
            if (cameraId == 0x02 && !_savedWrist)
            {
                _savedWrist = true;
                SavePng(target, "vr_teleop_wrist.png");
            }
        }
#endif
        BindPanel(cameraId == 0x01 ? frontPanel : wristPanel, target, cameraId == 0x01);
    }

    /// <summary>
    /// パネルへテクスチャを貼る。ランタイム専用 Material の mainTexture のみ更新する。
    /// </summary>
    private void BindPanel(Renderer panel, Texture2D target, bool isFront)
    {
        if (panel == null)
        {
            return;
        }
        if (!_warnedSamePanel && frontPanel != null && wristPanel != null
            && ReferenceEquals(frontPanel, wristPanel))
        {
            _warnedSamePanel = true;
            Debug.LogError("[VrTeleop] frontPanel == wristPanel（Inspector 割当ミス）");
        }

        EnsureUniquePanelMaterials();
        Material mat = isFront ? _frontMatInstance : _wristMatInstance;
        if (mat == null)
        {
            return;
        }
        // Unlit/Texture は _MainTex。専用インスタンスなので他パネルに漏れない。
        mat.mainTexture = target;
        if (mat.HasProperty("_BaseMap"))
        {
            mat.SetTexture("_BaseMap", target);
        }
        if (mat.HasProperty("_BaseColor"))
        {
            mat.SetColor("_BaseColor", Color.white);
        }
        if (mat.HasProperty("_Color"))
        {
            mat.SetColor("_Color", Color.white);
        }
        // 正しい Renderer に正しい Material が載っていることを毎フレーム保証
        if (panel.sharedMaterial != mat)
        {
            if (isFront && debugFrontPanel)
            {
                _frontMatRepairCount++;
                Material was = panel.sharedMaterial;
                Debug.LogWarning(
                    $"[VrTeleop][FrontDiag] REPAIR mat #{_frontMatRepairCount} " +
                    $"was={(was != null ? was.name : "null")} → {mat.name} " +
                    $"tex={(was != null && was.mainTexture != null ? was.mainTexture.name : "null")}"
                );
            }
            panel.SetPropertyBlock(null);
            panel.sharedMaterial = mat;
        }
    }

#if UNITY_EDITOR
    private static void SavePng(Texture2D tex, string fileName)
    {
        try
        {
            string path = System.IO.Path.Combine(Application.dataPath, "..", fileName);
            System.IO.File.WriteAllBytes(path, tex.EncodeToPNG());
            Debug.Log($"[VrTeleop] saved {path}");
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[VrTeleop] save png failed: {e.Message}");
        }
    }
#endif


    private static string F(float v)
    {
        return v.ToString("0.######", System.Globalization.CultureInfo.InvariantCulture);
    }

    private static string ExtractString(string json, string key)
    {
        // json.dumps 既定は `"key": "value"`（コロン後スペースあり）
        string needle = $"\"{key}\":";
        int i = json.IndexOf(needle, StringComparison.Ordinal);
        if (i < 0)
        {
            return "";
        }
        i += needle.Length;
        while (i < json.Length && (json[i] == ' ' || json[i] == '\t'))
        {
            i++;
        }
        if (i >= json.Length || json[i] != '"')
        {
            return "";
        }
        i++;
        int j = json.IndexOf('"', i);
        if (j < 0)
        {
            return "";
        }
        return json.Substring(i, j - i);
    }

    // --- UI helpers（Canvas Button から呼ぶ） ---

    public void UiSetRecord(bool v) => buttonRecord = v;
    public void UiSetSave(bool v) => buttonSave = v;
    public void UiSetDiscard(bool v) => buttonDiscard = v;
    public void UiSetReset(bool v) => buttonReset = v;
    public void UiSetGripper(float v) => gripper = v;
}

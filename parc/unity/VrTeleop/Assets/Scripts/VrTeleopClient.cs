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

    private float _sendPeriod;
    private float _sendAcc;
    private Texture2D _frontTex;
    private Texture2D _wristTex;
    private string _language = "";
    private bool _recording;

#if NATIVE_WEBSOCKET
    private WebSocket _ws;
#endif

    private void Awake()
    {
        _sendPeriod = 1f / Mathf.Max(1f, sendHz);
        _frontTex = new Texture2D(2, 2, TextureFormat.RGB24, false);
        _wristTex = new Texture2D(2, 2, TextureFormat.RGB24, false);
    }

    private async void Start()
    {
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

    private void Update()
    {
#if NATIVE_WEBSOCKET
        _ws?.DispatchMessageQueue();
#endif
        SampleXrButtons();
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

    /// <summary>XR Input / Inspector トグルからボタンを読む。</summary>
    private void SampleXrButtons()
    {
        // Inspector または外部からの上書きを許可。実機では Input Actions に接続する。
        if (rightController == null)
        {
            return;
        }
    }

    private void SendControl()
    {
        if (rightController == null)
        {
            return;
        }

        Vector3 p = rightController.position;
        Quaternion q = rightController.rotation;
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

        // Binary: camera_id + JPEG
        if (bytes[0] == 0x01 || bytes[0] == 0x02)
        {
            ApplyJpeg(bytes[0], bytes, 1);
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

    private void ApplyJpeg(byte cameraId, byte[] buffer, int offset)
    {
        int len = buffer.Length - offset;
        if (len < 2)
        {
            return;
        }
        byte[] jpeg = new byte[len];
        Buffer.BlockCopy(buffer, offset, jpeg, 0, len);
        Texture2D target = cameraId == 0x01 ? _frontTex : _wristTex;
        if (!target.LoadImage(jpeg))
        {
            return;
        }
        Renderer panel = cameraId == 0x01 ? frontPanel : wristPanel;
        if (panel != null)
        {
            panel.material.mainTexture = target;
        }
    }

    private static string F(float v)
    {
        return v.ToString("0.######", System.Globalization.CultureInfo.InvariantCulture);
    }

    private static string ExtractString(string json, string key)
    {
        string needle = $"\"{key}\":\"";
        int i = json.IndexOf(needle, StringComparison.Ordinal);
        if (i < 0)
        {
            return "";
        }
        i += needle.Length;
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

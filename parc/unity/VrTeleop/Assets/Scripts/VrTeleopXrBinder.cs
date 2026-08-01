using UnityEngine;
using UnityEngine.XR;
#if UNITY_INPUT_SYSTEM
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.XR;
#endif

/// <summary>
/// 右手コントローラ姿勢・ボタンを <see cref="VrTeleopClient"/> に流し込む。
/// OpenXR + Input System / 旧 InputDevices の両系統に対応。
/// Reset(Menu) は Quest では左手側にある点に注意。
/// </summary>
[RequireComponent(typeof(VrTeleopClient))]
public class VrTeleopXrBinder : MonoBehaviour
{
    public VrTeleopClient client;
    public XRNode node = XRNode.RightHand;

    [Tooltip("左手 Menu（≡）を Reset に使う。Quest 右手に Menu は無い")]
    public bool resetFromLeftMenu = true;

    [Header("Debug")]
    public bool logDeviceStatus = true;

    private InputDevice _rightDevice;
    private InputDevice _leftDevice;
    private bool _loggedRightOk;
    private bool _loggedRightMissing;

    private void Awake()
    {
        if (client == null)
        {
            client = GetComponent<VrTeleopClient>();
        }
    }

    private void Update()
    {
        if (client == null)
        {
            return;
        }

        bool ok = false;
#if UNITY_INPUT_SYSTEM
        ok = TryUpdateFromInputSystem();
#endif
        if (!ok)
        {
            ok = TryUpdateFromInputDevices();
        }

        if (ok)
        {
            if (!_loggedRightOk)
            {
                _loggedRightOk = true;
                Debug.Log("[VrTeleopXr] RightHand tracking OK");
            }
            return;
        }

        // Editor でコントローラ未接続は正常。キーボード操作で続行可。警告は一度だけ。
        if (logDeviceStatus && !_loggedRightMissing && Time.unscaledTime >= 3f)
        {
            _loggedRightMissing = true;
#if UNITY_EDITOR
            Debug.Log(
                "[VrTeleopXr] RightHand XR device not found（Editor ではよくある）。" +
                "矢印キーで EE 操作可。Quest Link / APK では OpenXR に Oculus Touch を追加し " +
                "Active Input Handling = Both。"
            );
#else
            Debug.LogWarning(
                "[VrTeleopXr] RightHand XR device not found. " +
                "OpenXR → Interaction Profiles に Oculus Touch を追加し、" +
                "Active Input Handling を Both にして APK 再ビルド。"
            );
#endif
        }
    }

#if UNITY_INPUT_SYSTEM
    /// <summary>Input System の XRController から読む（OpenXR 推奨経路）。</summary>
    private bool TryUpdateFromInputSystem()
    {
        XRController right = null;
        XRController left = null;
        foreach (var device in InputSystem.devices)
        {
            if (device is not XRController xr)
            {
                continue;
            }
            if (xr.usages.Contains(UnityEngine.InputSystem.CommonUsages.RightHand))
            {
                right = xr;
            }
            if (xr.usages.Contains(UnityEngine.InputSystem.CommonUsages.LeftHand))
            {
                left = xr;
            }
        }

        if (right == null)
        {
            return false;
        }

        if (client.rightController != null)
        {
            Vector3 pos = right.devicePosition.ReadValue();
            Quaternion rot = right.deviceRotation.ReadValue();
            client.rightController.SetPositionAndRotation(pos, rot);
        }

        client.gripper = right.trigger.ReadValue();
        client.buttonRecord = right.primaryButton.isPressed;
        client.buttonSave = right.secondaryButton.isPressed;
        client.buttonDiscard = right.gripButton.isPressed;

        if (resetFromLeftMenu && left != null)
        {
            // Quest: Menu は左手。XRController に menu が無い場合は false のまま。
            var menuCtrl = left.TryGetChildControl<UnityEngine.InputSystem.Controls.ButtonControl>("menu");
            if (menuCtrl != null)
            {
                client.buttonReset = menuCtrl.isPressed;
            }
            else
            {
                // 左手 secondary (Y) を Reset 代替
                client.buttonReset = left.secondaryButton.isPressed;
            }
        }

        return true;
    }
#endif

    /// <summary>旧 XR InputDevices API（Active Input Handling = Both のとき有効）。</summary>
    private bool TryUpdateFromInputDevices()
    {
        if (!_rightDevice.isValid)
        {
            _rightDevice = InputDevices.GetDeviceAtXRNode(node);
        }
        if (!_rightDevice.isValid)
        {
            return false;
        }

        if (_rightDevice.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 pos)
            && _rightDevice.TryGetFeatureValue(CommonUsages.deviceRotation, out Quaternion rot)
            && client.rightController != null)
        {
            client.rightController.SetPositionAndRotation(pos, rot);
        }

        if (_rightDevice.TryGetFeatureValue(CommonUsages.trigger, out float trigger))
        {
            client.gripper = trigger;
        }
        if (_rightDevice.TryGetFeatureValue(CommonUsages.primaryButton, out bool primary))
        {
            client.buttonRecord = primary;
        }
        if (_rightDevice.TryGetFeatureValue(CommonUsages.secondaryButton, out bool secondary))
        {
            client.buttonSave = secondary;
        }
        if (_rightDevice.TryGetFeatureValue(CommonUsages.gripButton, out bool gripBtn))
        {
            client.buttonDiscard = gripBtn;
        }

        if (resetFromLeftMenu)
        {
            if (!_leftDevice.isValid)
            {
                _leftDevice = InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);
            }
            if (_leftDevice.isValid)
            {
                if (_leftDevice.TryGetFeatureValue(CommonUsages.menuButton, out bool menu))
                {
                    client.buttonReset = menu;
                }
                else if (_leftDevice.TryGetFeatureValue(CommonUsages.secondaryButton, out bool yBtn))
                {
                    // Menu が取れない端末では左手 Y を Reset に使う
                    client.buttonReset = yBtn;
                }
            }
        }
        else if (_rightDevice.TryGetFeatureValue(CommonUsages.menuButton, out bool menuRight))
        {
            client.buttonReset = menuRight;
        }

        return true;
    }
}

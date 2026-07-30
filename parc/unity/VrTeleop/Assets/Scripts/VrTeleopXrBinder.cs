using UnityEngine;
using UnityEngine.XR;

/// <summary>
/// 右手コントローラの CommonUsages を VrTeleopClient に流し込む。
/// XR Interaction Toolkit 無しでも動く最小バインド。
/// </summary>
[RequireComponent(typeof(VrTeleopClient))]
public class VrTeleopXrBinder : MonoBehaviour
{
    public VrTeleopClient client;
    public XRNode node = XRNode.RightHand;

    private InputDevice _device;

    private void Awake()
    {
        if (client == null)
        {
            client = GetComponent<VrTeleopClient>();
        }
    }

    private void Update()
    {
        if (!_device.isValid)
        {
            _device = InputDevices.GetDeviceAtXRNode(node);
            if (!_device.isValid)
            {
                return;
            }
        }

        if (_device.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 pos)
            && _device.TryGetFeatureValue(CommonUsages.deviceRotation, out Quaternion rot)
            && client.rightController != null)
        {
            client.rightController.SetPositionAndRotation(pos, rot);
        }

        if (_device.TryGetFeatureValue(CommonUsages.trigger, out float trigger))
        {
            client.gripper = trigger;
        }

        // primaryButton = A (右手), secondaryButton = B
        if (_device.TryGetFeatureValue(CommonUsages.primaryButton, out bool primary))
        {
            client.buttonRecord = primary;
        }
        if (_device.TryGetFeatureValue(CommonUsages.secondaryButton, out bool secondary))
        {
            client.buttonSave = secondary;
        }
        if (_device.TryGetFeatureValue(CommonUsages.gripButton, out bool gripBtn))
        {
            client.buttonDiscard = gripBtn;
        }
        if (_device.TryGetFeatureValue(CommonUsages.menuButton, out bool menu))
        {
            client.buttonReset = menu;
        }
    }
}

using UnityEngine;

/// <summary>
/// 映像パネル用 HUD 追従。
/// Main Camera（ステレオ眼）の子にすると左右眼で二重像・左右ずれが出るため、
/// カメラ外のルートを頭姿勢に合わせる。
/// XR カメラ更新直後に合わせるため <see cref="Application.onBeforeRender"/> のみ使う
/// （LateUpdate と二重同期するとちらつく）。
/// </summary>
public class VrTeleopHudFollow : MonoBehaviour
{
    [Tooltip("通常は XR Main Camera（TrackedPoseDriver 付き）")]
    public Transform head;

    [Tooltip("頭基準のローカルオフセット（位置のみ。回転は頭に一致）")]
    public Vector3 localPositionOffset = Vector3.zero;

    private void OnEnable()
    {
        Application.onBeforeRender += SyncToHead;
    }

    private void OnDisable()
    {
        Application.onBeforeRender -= SyncToHead;
    }

    private void SyncToHead()
    {
        if (head == null)
        {
            return;
        }
        transform.SetPositionAndRotation(
            head.TransformPoint(localPositionOffset),
            head.rotation
        );
    }
}

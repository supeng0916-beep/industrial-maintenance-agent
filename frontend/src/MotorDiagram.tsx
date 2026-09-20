/** 中性设备示意，不以颜色或动画暗示电机正在运行或健康。 */
export function MotorDiagram() {
  return <figure className="motor-diagram">
    <svg viewBox="0 0 300 180" role="img" aria-label="模拟电机A示意，温度测点位于电机外壳；示意不表示运行状态">
      <g fill="none" stroke="#4a4f4b" strokeWidth="1">
        <path d="M18 150H285M35 139v22M265 139v22M48 153v6m15-6v6m15-6v6m15-6v6m15-6v6m15-6v6m15-6v6m15-6v6m15-6v6m15-6v6m15-6v6m15-6v6m15-6v6m15-6v6" />
      </g>
      <g stroke="#6d736e" strokeWidth="2" strokeLinejoin="round">
        <path d="M85 126v15h25l6-15m79 0v15h23v-15" fill="#3c413e" />
        <path d="M61 69h25v53H61z" fill="#434845" />
        <rect x="78" y="54" width="143" height="78" rx="13" fill="#4a4f4b" />
        <path d="M91 66v55m13-57v59m13-59v59m13-59v59m13-59v59m13-59v59m13-59v59m13-59v59" />
        <path d="M196 55v76" />
        <path d="M221 83h42v19h-42" fill="#3c413e" />
        <path d="M110 54V39h42v15" fill="#434845" />
      </g>
      <path d="M182 79V23h64" stroke="#ffb000" strokeWidth="1.5" fill="none" />
      <circle cx="182" cy="79" r="5" fill="#ffb000" stroke="#2e3230" strokeWidth="2" />
      <text x="208" y="15" fill="#a9aca0" fontSize="13">温度测点</text>
    </svg>
    <figcaption>电机外壳测温示意<span>示意图不表示运行状态</span></figcaption>
  </figure>
}

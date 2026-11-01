/** 功能：在 Blockly 积木中内嵌角度滑杆，字段仍以弧度保存。
 * Created on 2026-11-02; Updated on 2026-11-02
 * @author: https://github.com/Linmoqian
 */
import * as Blockly from "blockly/core";

export class JointAngleSlider extends Blockly.FieldNumber {
  private slider: HTMLInputElement | undefined;
  private output: HTMLOutputElement | undefined;

  constructor(value: number, lower: number, upper: number,
    private readonly label: string, private readonly onSlide: (value: number) => void) {
    super(value, lower, upper);
  }

  override initView(): void {
    super.initView();
    this.textElement_?.setAttribute("display", "none");
    this.borderRect_?.setAttribute("display", "none");
    const foreign = document.createElementNS("http://www.w3.org/2000/svg", "foreignObject");
    foreign.setAttribute("width", "180"); foreign.setAttribute("height", "44");
    const control = document.createElement("div");
    control.className = "joint-angle-control";
    const slider = document.createElement("input");
    slider.type = "range"; slider.className = "joint-angle-slider";
    slider.min = String(this.getMin() * 180 / Math.PI);
    slider.max = String(this.getMax() * 180 / Math.PI);
    slider.step = "any";
    slider.setAttribute("aria-label", `${this.label}角度`);
    const output = document.createElement("output");
    output.className = "joint-angle-value";
    for (const type of ["pointerdown", "mousedown", "touchstart", "keydown"]) {
      control.addEventListener(type, (event) => event.stopPropagation());
    }
    slider.addEventListener("input", () => {
      this.setValue(Number(slider.value) * Math.PI / 180);
      this.render_();
      this.onSlide(Number(this.getValue()));
    });
    control.append(slider, output); foreign.append(control); this.fieldGroup_?.append(foreign);
    this.slider = slider; this.output = output;
    this.render_();
  }

  protected override render_(): void {
    this.size_ = new Blockly.utils.Size(180, 44);
    const degrees = Number(this.getValue()) * 180 / Math.PI;
    if (this.slider) { this.slider.value = String(degrees); this.slider.setAttribute("aria-valuetext", `${degrees.toFixed(1)} 度`); }
    if (this.output) this.output.value = `${degrees.toFixed(1)}°`;
  }

  protected override showEditor_(): void { /* 使用内嵌滑杆，不打开数值编辑弹窗。 */ }
}

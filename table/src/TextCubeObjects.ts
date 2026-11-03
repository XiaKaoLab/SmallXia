/** 功能：按仿真真实刚体姿态显示文字方块，文字贴图不决定识别结果。
 * Created on 2026-11-03; Updated on 2026-11-03
 * @author: https://github.com/Linmoqian
 */
import * as THREE from "three";
export interface TextCubeSnapshot { letter: string; position: number[]; quaternion: number[]; half_size: number; target: boolean }
export class TextCubeObjects {
  readonly group = new THREE.Group();
  private readonly geometry = new THREE.BoxGeometry(1,1,1);
  private readonly objects = new Map<string,THREE.Mesh>();
  update(items: TextCubeSnapshot[], offset: THREE.Vector3): void {
    for (const item of items) {
      if (item.position.length!==3 || item.quaternion.length!==4 || ![...item.position,...item.quaternion,item.half_size].every(Number.isFinite)) continue;
      let mesh=this.objects.get(item.letter);
      if (!mesh) {
        const canvas=document.createElement("canvas");canvas.width=512;canvas.height=512;
        const context=canvas.getContext("2d");if (!context) continue;
        context.fillStyle="#f4e0ae";context.fillRect(0,0,512,512);
        context.font=`bold ${Math.min(300,Math.floor(420/Math.max(item.letter.length,1)))}px Microsoft YaHei`;
        context.textAlign="center";context.textBaseline="middle";context.fillStyle="#aa1e18";context.fillText(item.letter,256,256);
        const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
        mesh=new THREE.Mesh(this.geometry,new THREE.MeshStandardMaterial({map:texture,roughness:.7}));
        mesh.name=`text_cube_${item.letter}`;this.group.add(mesh);this.objects.set(item.letter,mesh);
      }
      mesh.position.fromArray(item.position).add(offset);mesh.scale.setScalar(item.half_size*2);
      const [w,x,y,z]=item.quaternion;mesh.quaternion.set(x,y,z,w);
    }
  }
  dispose(): void {
    for (const mesh of this.objects.values()) {
      const material=mesh.material as THREE.MeshStandardMaterial;material.map?.dispose();material.dispose();
    }
    this.geometry.dispose();this.objects.clear();this.group.clear();this.group.removeFromParent();
  }
}

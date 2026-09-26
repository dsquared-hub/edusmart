// <model-viewer> — веб-компонент Google для 3D (glb). Типы для JSX.
import type React from "react";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "model-viewer": React.DetailedHTMLProps<React.HTMLAttributes<HTMLElement>, HTMLElement> & {
        src?: string;
        poster?: string;
        alt?: string;
        loading?: "auto" | "lazy" | "eager";
        reveal?: "auto" | "manual";
        "camera-controls"?: boolean;
        "disable-zoom"?: boolean;
        "disable-pan"?: boolean;
        "disable-tap"?: boolean;
        "touch-action"?: string;
        "interaction-prompt"?: "auto" | "none";
        "camera-orbit"?: string;
        "min-camera-orbit"?: string;
        "max-camera-orbit"?: string;
        "field-of-view"?: string;
        "shadow-intensity"?: string;
        "shadow-softness"?: string;
        exposure?: string;
        "environment-image"?: string;
        "interpolation-decay"?: string;
      };
    }
  }
}

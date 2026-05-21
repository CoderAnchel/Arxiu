import type { ButtonHTMLAttributes } from "react";

import styles from "./Button.module.css";

type Variant = "default" | "primary" | "danger" | "ghost";
type Size = "default" | "sm";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
};

export function Button({
  variant = "default",
  size = "default",
  className,
  children,
  ...rest
}: ButtonProps) {
  const cls = [
    styles.btn,
    variant === "primary" ? styles.primary : "",
    variant === "danger" ? styles.danger : "",
    variant === "ghost" ? styles.ghost : "",
    size === "sm" ? styles.sm : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button type="button" className={cls} {...rest}>
      {children}
    </button>
  );
}

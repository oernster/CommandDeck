import styles from "./TrayRuntimeIndicator.module.css";

const DEFAULT_TOOLTIP =
  "Command Deck runs in your system tray (bottom-right of your screen). You can reopen it from there at any time.";

type TrayRuntimeIndicatorProps = {
  label?: string;
  tooltip?: string;
};

export function TrayRuntimeIndicator({
  label = "Running in system tray",
  tooltip = DEFAULT_TOOLTIP,
}: TrayRuntimeIndicatorProps) {
  return (
    <span className={styles.root} title={tooltip} aria-label={label}>
      <span className={styles.dot} aria-hidden="true" />
      <span className={styles.label}>{label}</span>
    </span>
  );
}


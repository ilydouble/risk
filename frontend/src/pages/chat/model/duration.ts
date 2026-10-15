export function formatTurnDuration(milliseconds: number, english: boolean): string {
  const totalSeconds = Math.floor(Math.max(0, milliseconds) / 1000);
  const seconds = totalSeconds % 60;
  const minutes = Math.floor(totalSeconds / 60) % 60;
  const hours = Math.floor(totalSeconds / 3600);
  if (hours) return english ? `${hours}h ${minutes}m ${seconds}s` : `${hours}小时 ${minutes}分 ${seconds}秒`;
  if (minutes) return english ? `${minutes}m ${seconds}s` : `${minutes}分 ${seconds}秒`;
  return `${seconds}s`;
}

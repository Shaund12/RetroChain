export function useToast() {
  const notify = (message: string) => {
    const ev = new CustomEvent<string>("rc-toast", { detail: message });
    window.dispatchEvent(ev);
  };
  return { notify };
}

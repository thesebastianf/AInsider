export function openSymbolOverview(symbolOrIsin) {
  if (!symbolOrIsin) return;
  window.dispatchEvent(new CustomEvent('open-symbol-overview', { detail: symbolOrIsin }));
}

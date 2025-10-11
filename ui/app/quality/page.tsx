// This page has been deprecated. Use /preview instead.
export default function QualityPage() {
  if (typeof window !== 'undefined') {
    window.location.href = '/preview';
  }
  return null;
}

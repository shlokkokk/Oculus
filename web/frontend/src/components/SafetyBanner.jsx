import { useState } from 'react';
import { ShieldAlert, X } from 'lucide-react';

export default function SafetyBanner() {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  return (
    <div className="safety-banner">
      <ShieldAlert size={16} />
      <span>
        <strong>Authorized use only.</strong> Only scan targets you own or have explicit written permission to test.
      </span>
      <X size={14} className="close-btn" onClick={() => setDismissed(true)} />
    </div>
  );
}

import React, { useState } from 'react';
import { CircleAlert, Sparkles } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { DaxCode } from '../lib/dax';
import { errorMessage } from '../lib/errors';

interface Rewrite {
  ai_generated: boolean;
  ai_model?: string;
  suggested_rewrite?: string;
  rewrite_explanation?: string;
  recommendation?: string;
  error?: string;
}

/** Asks the local engine for a rewrite of one DAX expression. Advisory text only; nothing is applied. */
export const DaxRewriteAdvisor: React.FC<{ dax: string; ruleId?: string; evidence?: string }> = ({ dax, ruleId = 'DAX_SUSPICIOUS_PATTERN', evidence = '' }) => {
  const [rewrite, setRewrite] = useState<Rewrite | null>(null);
  const [asking, setAsking] = useState(false);

  const ask = async () => {
    setAsking(true); setRewrite(null);
    try {
      const res = await apiFetch('/api/dax/rewrite', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rule_id: ruleId, dax_expression: dax, evidence }),
      });
      if (!res.ok) throw new Error(`The engine answered ${res.status}.`);
      setRewrite(await res.json());
    } catch (e) {
      setRewrite({ ai_generated: false, error: errorMessage(e) || 'The rewrite request failed.' });
    } finally {
      setAsking(false);
    }
  };

  return (
    <div className="blk">
      <div className="label">DAX rewrite advisor</div>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        Sends this measure's DAX to a language model when <span className="mono">GROQ_API_KEY</span> is set; otherwise shows pbiscan's static guidance. The result is text for you to review.
      </p>
      <div className="actions">
        <button className="btn btn-sm btn-primary" onClick={ask} disabled={asking || !dax.trim()}><Sparkles aria-hidden="true" />{asking ? 'Asking…' : 'Suggest a rewrite'}</button>
      </div>
      {rewrite && (rewrite.error ? <div className="notice error"><CircleAlert aria-hidden="true" /><span className="grow">{rewrite.error}</span></div>
        : rewrite.ai_generated && rewrite.suggested_rewrite ? (
          <>
            <div className="label">Suggested rewrite · {rewrite.ai_model} · review before using</div>
            <DaxCode code={rewrite.suggested_rewrite} />
            {rewrite.rewrite_explanation && <p className="ink-2" style={{ margin: 0, fontSize: 13.5 }}>{rewrite.rewrite_explanation}</p>}
          </>
        ) : <div className="notice"><span className="grow"><strong>Static guidance:</strong> {rewrite.recommendation}</span></div>)}
    </div>
  );
};

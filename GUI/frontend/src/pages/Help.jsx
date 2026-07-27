import React from 'react';

const Help = () => (
    <div className="container py-3">
        <h2 className="mb-3">Help</h2>
        <p className="mb-3">
            Terminology: <strong>HL</strong> = <strong>High-Level</strong>,
            <strong> LL</strong> = <strong>Low-Level</strong>.
        </p>

        <div className="card shadow-sm mb-3">
            <div className="card-header bg-light fw-semibold">Quick Start</div>
            <div className="card-body">
                <ol className="mb-0">
                    <li>Write both prompt descriptions in the Prompt step.</li>
                    <li>Run consistency validation (or skip if you accept the risk).</li>
                    <li>Generate HL KB and review the sections.</li>
                    <li>Generate LL KB, then export the final <code>.pl</code> file.</li>
                </ol>
            </div>
        </div>

        <div className="card shadow-sm mb-3">
            <div className="card-header bg-light fw-semibold">Useful Controls</div>
            <div className="card-body">
                <ul className="mb-0">
                    <li>Use the LLM dropdown to choose a backend config before checks/generation.</li>
                    <li>Enable automatic verification to retry generation with consistency checks.</li>
                    <li>
                        Switch to combined view if you prefer editing all generated sections in one
                        textarea.
                    </li>
                    <li>Use Download .pl after LL generation to export a planner-ready file.</li>
                </ul>
            </div>
        </div>

        <div className="card shadow-sm mb-3">
            <div className="card-header bg-light fw-semibold">Troubleshooting</div>
            <div className="card-body">
                <ul className="mb-0">
                    <li>If the LLM list is empty, check backend availability and LLM config files.</li>
                    <li>
                        If LL generation fails, verify HL <code>kb/init/goal/actions</code> fields are
                        complete.
                    </li>
                    <li>
                        If export is blocked, fill every LL section:
                        <code> kb/init/goal/ll_actions/mappings</code>.
                    </li>
                    <li>
                        If generation responses are partial, disable combined view and inspect each
                        section separately.
                    </li>
                </ul>
            </div>
        </div>

        <div className="alert alert-secondary mb-0" role="alert">
            Additional project details: <a href="https://github.com/icosac/plantor_improved">PLANTOR repository</a>.
        </div>
    </div>
);

export default Help;

import React from 'react';

const About = () => (
    <div className="container py-3">
        <div className="mb-4">
            <h2 className="mb-2">About PLANTOR Enhanced</h2>
            <p className="mb-2">
                PLANTOR (PLanning with Natural language for Task-Oriented Robots) Enhanced
                transforms natural-language instructions into structured knowledge and planning
                artifacts for robotic execution.
            </p>
            <p className="mb-2">
                In this GUI, <strong>HL</strong> means <strong>High-Level</strong> and
                <strong> LL</strong> means <strong>Low-Level</strong>.
            </p>
            <p className="mb-0">
                The framework has three core modules:
                <strong> KMS</strong> (LLM-driven knowledge generation),
                <strong> TP</strong> (task planning), and
                <strong> EXE</strong> (behavior-tree execution). This GUI coordinates the full
                workflow end-to-end.
            </p>
        </div>

        <div className="card shadow-sm mb-4">
            <div className="card-header bg-light fw-semibold">Workflow Steps</div>
            <div className="card-body">
                <ol className="mb-0">
                    <li className="mb-2">
                        <strong>Prompt</strong>: provide high-level and low-level task
                        descriptions.
                    </li>
                    <li className="mb-2">
                        <strong>Consistency check</strong>: validate the two descriptions, or
                        explicitly skip validation.
                    </li>
                    <li className="mb-2">
                        <strong>HL KB generation</strong>: generate high-level
                        <code> kb/init/goal/actions </code>
                        content.
                    </li>
                    <li className="mb-2">
                        <strong>LL KB generation</strong>: generate low-level
                        <code> kb/init/goal/ll_actions/mappings </code>
                        using the low-level prompt plus current HL sections.
                    </li>
                    <li className="mb-2">
                        <strong>Planning</strong>: planned area for planner execution controls.
                    </li>
                    <li className="mb-2">
                        <strong>Plan</strong>: planned area for inspecting and refining plans.
                    </li>
                    <li className="mb-2">
                        <strong>Enablers</strong>: inspect causal and assumption enabler
                        relationships.
                    </li>
                    <li className="mb-2">
                        <strong>Optimized STN</strong>: generate and inspect the optimized
                        Simple Temporal Network.
                    </li>
                    <li>
                        <strong>BT generation</strong>: extract the behavior tree, inspect the
                        graph visualization, and download the XML artifact.
                    </li>
                </ol>
            </div>
        </div>

        <div className="alert alert-info mb-0" role="alert">
            <strong>Progression rule:</strong> steps unlock only when required outputs are
            available for the current stage.
        </div>
    </div>
);

export default About;

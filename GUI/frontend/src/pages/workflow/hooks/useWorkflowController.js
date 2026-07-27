import { useEffect, useMemo, useState } from 'react';
import {
    generateOptimizedBehaviorTree,
    generateHighLevelKB,
    generateHighLevelPlanVisualization,
    generateOptimizedStnVisualization,
    generateLowLevelKB,
    listLlmConfigs,
    stopHighLevelPlanGeneration,
    validateDescriptions,
} from '../../../api';
import {
    DEFAULT_VERIFY_RETRY_BUDGET,
    MIN_VERIFY_RETRY_BUDGET,
    STEPS,
} from '../constants';
import {
    buildHlCombined,
    buildLlCombined,
    buildLlExportWithHlActions,
    getHlInputsForLlGeneration,
    getLlInputsForExport,
    parseHlCombined,
    parseLlCombined,
} from '../utils/kbSections';

const useWorkflowController = () => {
    const apiBaseUrl = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000/api';
    const [highLevelDesc, setHighLevelDesc] = useState('');
    const [lowLevelDesc, setLowLevelDesc] = useState('');
    const [currentStep, setCurrentStep] = useState(0);
    const [maxReachedStep, setMaxReachedStep] = useState(0);

    const [llmConfigs, setLlmConfigs] = useState([]);
    const [selectedLlm, setSelectedLlm] = useState('');
    const [llmLoadError, setLlmLoadError] = useState('');

    const [isChecking, setIsChecking] = useState(false);
    const [validationStatus, setValidationStatus] = useState(null);
    const [skipConsistencyCheck, setSkipConsistencyCheck] = useState(false);

    const [isGeneratingHlKb, setIsGeneratingHlKb] = useState(false);
    const [hlGenerationStatus, setHlGenerationStatus] = useState(null);
    const [verifyHlGeneration, setVerifyHlGeneration] = useState(false);
    const [verifyHlRetries, setVerifyHlRetries] = useState(DEFAULT_VERIFY_RETRY_BUDGET);

    const [isGeneratingLlKb, setIsGeneratingLlKb] = useState(false);
    const [llGenerationStatus, setLlGenerationStatus] = useState(null);
    const [verifyLlGeneration, setVerifyLlGeneration] = useState(false);
    const [verifyLlRetries, setVerifyLlRetries] = useState(DEFAULT_VERIFY_RETRY_BUDGET);
    const [skipLlGeneration, setSkipLlGeneration] = useState(false);

    const [hlKbContent, setHlKbContent] = useState('');
    const [hlInitContent, setHlInitContent] = useState('');
    const [hlGoalContent, setHlGoalContent] = useState('');
    const [hlActionsContent, setHlActionsContent] = useState('');
    const [hlCombinedView, setHlCombinedView] = useState(false);
    const [hlCombinedContent, setHlCombinedContent] = useState('');

    const [llKbContent, setLlKbContent] = useState('');
    const [llInitContent, setLlInitContent] = useState('');
    const [llGoalContent, setLlGoalContent] = useState('');
    const [llActionsContent, setLlActionsContent] = useState('');
    const [llMappingsContent, setLlMappingsContent] = useState('');
    const [llCombinedView, setLlCombinedView] = useState(false);
    const [llCombinedContent, setLlCombinedContent] = useState('');

    const [isGeneratingHlPlan, setIsGeneratingHlPlan] = useState(false);
    const [hlPlanStatus, setHlPlanStatus] = useState(null);
    const [hlPlanFound, setHlPlanFound] = useState(false);
    const [planningMaxDepth, setPlanningMaxDepth] = useState(10);
    const [planningTimeoutSeconds, setPlanningTimeoutSeconds] = useState(180);
    const [hlPlanHtml, setHlPlanHtml] = useState('');
    const [hlPlanUrl, setHlPlanUrl] = useState('');
    const [hlPlanLog, setHlPlanLog] = useState('');
    const [hlPlanSteps, setHlPlanSteps] = useState([]);
    const [toPlanSteps, setToPlanSteps] = useState([]);
    const [enablersHtml, setEnablersHtml] = useState('');
    const [enablersUrl, setEnablersUrl] = useState('');
    const [enablerTerms, setEnablerTerms] = useState([]);
    const [planWithEnablers, setPlanWithEnablers] = useState([]);
    const [isGeneratingOptimizedStn, setIsGeneratingOptimizedStn] = useState(false);
    const [optimizedStnGenerated, setOptimizedStnGenerated] = useState(false);
    const [optimizedStnStatus, setOptimizedStnStatus] = useState(null);
    const [optimizedStnHtml, setOptimizedStnHtml] = useState('');
    const [optimizedStnUrl, setOptimizedStnUrl] = useState('');
    const [optimizedStnExecutionGraphHtml, setOptimizedStnExecutionGraphHtml] = useState('');
    const [optimizedStnExecutionGraphUrl, setOptimizedStnExecutionGraphUrl] = useState('');
    const [optimizedStnLog, setOptimizedStnLog] = useState('');
    const [isGeneratingBt, setIsGeneratingBt] = useState(false);
    const [btStatus, setBtStatus] = useState(null);
    const [btHtml, setBtHtml] = useState('');
    const [btUrl, setBtUrl] = useState('');
    const [btXml, setBtXml] = useState('');
    const [btXmlUrl, setBtXmlUrl] = useState('');
    const [btLog, setBtLog] = useState('');

    const progress = useMemo(() => {
        if (STEPS.length <= 1) return 0;
        return (currentStep / (STEPS.length - 1)) * 100;
    }, [currentStep]);

    useEffect(() => {
        let active = true;

        const loadLlmConfigs = async () => {
            try {
                const response = await listLlmConfigs();
                if (!active) {
                    return;
                }

                const configs = Array.isArray(response.configs) ? response.configs : [];
                setLlmConfigs(configs);

                const serverSelected = typeof response.selected === 'string' ? response.selected : '';
                if (serverSelected && configs.includes(serverSelected)) {
                    setSelectedLlm(serverSelected);
                } else if (configs.length > 0) {
                    setSelectedLlm(configs[0]);
                } else {
                    setSelectedLlm('');
                }
                setLlmLoadError('');
            } catch (error) {
                if (!active) {
                    return;
                }
                setLlmLoadError(error.message || 'Unable to load available LLM configs.');
            }
        };

        loadLlmConfigs();

        return () => { active = false; };
    }, []);

    const promptsReady = highLevelDesc.trim() !== '' && lowLevelDesc.trim() !== '';
    const consistencyPassed = validationStatus?.type === 'success';
    const consistencyCanProceed = skipConsistencyCheck || consistencyPassed;
    const hlGenerated = hlKbContent.trim() !== '';
    const llGenerated = llKbContent.trim() !== '';

    const canProceedFromStep = (stepIndex) => {
        if (stepIndex === 0) return promptsReady;
        if (stepIndex === 1) return consistencyCanProceed;
        if (stepIndex === 2) return hlGenerated;
        if (stepIndex === 3) return skipLlGeneration || llGenerated;
        if (stepIndex === 4) return hlPlanFound;
        if (stepIndex === 7) return optimizedStnGenerated;
        return true;
    };

    const canAccessStep = (stepIndex) => stepIndex <= maxReachedStep;

    const moveStep = (direction) => {
        if (direction < 0) {
            setCurrentStep((prev) => Math.max(0, prev + direction));
            return;
        }

        setCurrentStep((prev) => {
            if (!canProceedFromStep(prev)) {
                return prev;
            }
            const shouldSkipLlStep = direction > 0 && prev === 2 && skipLlGeneration;
            const nextIndex = shouldSkipLlStep ? prev + 2 : prev + direction;
            const next = Math.min(STEPS.length - 1, nextIndex);
            if (next > prev) {
                setMaxReachedStep((currentMax) => Math.max(currentMax, next));
            }
            return next;
        });
    };

    const goToStep = (stepIndex) => {
        if (!canAccessStep(stepIndex)) {
            return;
        }
        setCurrentStep(stepIndex);
    };

    const resetConsistencyState = () => {
        setValidationStatus(null);
    };

    const handleSkipConsistencyCheckChange = (checked) => {
        setSkipConsistencyCheck(checked);
        if (checked) {
            setValidationStatus(null);
        }
    };

    const handleHighLevelDescChange = (value) => {
        setHighLevelDesc(value);
        resetConsistencyState();
    };

    const handleLowLevelDescChange = (value) => {
        setLowLevelDesc(value);
        resetConsistencyState();
    };

    const runConsistencyCheck = async () => {
        if (!highLevelDesc.trim() || !lowLevelDesc.trim()) {
            setValidationStatus({
                type: 'error',
                message: 'Please fill both prompt descriptions before running consistency check.',
            });
            return;
        }

        setIsChecking(true);
        setSkipConsistencyCheck(false);
        setValidationStatus(null);

        try {
            const result = await validateDescriptions(highLevelDesc, lowLevelDesc, selectedLlm);
            if (result.isValid) {
                setValidationStatus({
                    type: 'success',
                    message: 'Consistency check passed.',
                });
            } else {
                setValidationStatus({
                    type: 'error',
                    message: result.error || 'Consistency check failed.',
                });
            }
        } catch (error) {
            setValidationStatus({
                type: 'error',
                message: error.message || 'Consistency check request failed.',
            });
        } finally {
            setIsChecking(false);
        }
    };

    const autoResizeTextarea = (textarea) => {
        if (!textarea) return;
        textarea.style.height = 'auto';
        textarea.style.height = `${textarea.scrollHeight}px`;
    };

    const handleAutoResizeTextarea = (event) => {
        autoResizeTextarea(event.target);
    };

    const parseRetryBudget = (value, fallback = DEFAULT_VERIFY_RETRY_BUDGET) => {
        const parsed = Number.parseInt(value, 10);
        if (Number.isNaN(parsed)) {
            return fallback;
        }
        return Math.max(MIN_VERIFY_RETRY_BUDGET, parsed);
    };

    const parsePlannerInteger = (value, fallback, minValue) => {
        const parsed = Number.parseInt(value, 10);
        if (Number.isNaN(parsed)) {
            return fallback;
        }
        return Math.max(minValue, parsed);
    };

    const handleHlCombinedToggle = (checked) => {
        setHlCombinedView(checked);
        if (checked) {
            setHlCombinedContent(buildHlCombined(hlKbContent, hlInitContent, hlGoalContent, hlActionsContent));
        }
        requestAnimationFrame(() => {
            document.querySelectorAll('textarea.auto-resize').forEach((t) => autoResizeTextarea(t));
        });
    };

    const handleHlCombinedChange = (value) => {
        setHlCombinedContent(value);
        const parsed = parseHlCombined(value);
        if (parsed.kb !== null) setHlKbContent(parsed.kb);
        if (parsed.init !== null) setHlInitContent(parsed.init);
        if (parsed.goal !== null) setHlGoalContent(parsed.goal);
        if (parsed.actions !== null) setHlActionsContent(parsed.actions);
    };

    const handleLlCombinedToggle = (checked) => {
        setLlCombinedView(checked);
        if (checked) {
            setLlCombinedContent(buildLlCombined(llKbContent, llInitContent, llGoalContent, llActionsContent, llMappingsContent));
        }
        requestAnimationFrame(() => {
            document.querySelectorAll('textarea.auto-resize').forEach((t) => autoResizeTextarea(t));
        });
    };

    const handleLlCombinedChange = (value) => {
        setLlCombinedContent(value);
        const parsed = parseLlCombined(value);
        if (parsed.kb !== null) setLlKbContent(parsed.kb);
        if (parsed.init !== null) setLlInitContent(parsed.init);
        if (parsed.goal !== null) setLlGoalContent(parsed.goal);
        if (parsed.ll_actions !== null) setLlActionsContent(parsed.ll_actions);
        if (parsed.mappings !== null) setLlMappingsContent(parsed.mappings);
    };

    const downloadLlKbWithHlActions = () => {
        const hlInputs = getHlInputsForLlGeneration({
            hlCombinedView,
            hlCombinedContent,
            hlKbContent,
            hlInitContent,
            hlGoalContent,
            hlActionsContent,
        });
        const llInputs = getLlInputsForExport({
            llCombinedView,
            llCombinedContent,
            llKbContent,
            llInitContent,
            llGoalContent,
            llActionsContent,
            llMappingsContent,
        });

        const missing = [];
        if (!hlInputs.actions.trim()) missing.push('HL actions');
        if (!llInputs.kb.trim()) missing.push('LL kb');
        if (!llInputs.init.trim()) missing.push('LL init');
        if (!llInputs.goal.trim()) missing.push('LL goal');
        if (!llInputs.llActions.trim()) missing.push('LL actions');
        if (!llInputs.mappings.trim()) missing.push('LL mappings');

        if (missing.length > 0) {
            setLlGenerationStatus({
                type: 'error',
                message: `Cannot export .pl file. Missing sections: ${missing.join(', ')}.`,
            });
            return;
        }

        const content = `${buildLlExportWithHlActions(hlInputs.actions, llInputs)}\n`;
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'll_kb_with_hl_actions.pl';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);

        setLlGenerationStatus({
            type: 'success',
            message: 'Downloaded ll_kb_with_hl_actions.pl.',
        });
    };

    const downloadHlKb = () => {
        const hlInputs = getHlInputsForLlGeneration({
            hlCombinedView,
            hlCombinedContent,
            hlKbContent,
            hlInitContent,
            hlGoalContent,
            hlActionsContent,
        });

        const missing = [];
        if (!hlInputs.kb.trim()) missing.push('HL kb');
        if (!hlInputs.init.trim()) missing.push('HL init');
        if (!hlInputs.goal.trim()) missing.push('HL goal');
        if (!hlInputs.actions.trim()) missing.push('HL actions');

        if (missing.length > 0) {
            setHlGenerationStatus({
                type: 'error',
                message: `Cannot export .pl file. Missing sections: ${missing.join(', ')}.`,
            });
            return;
        }

        const content = `${buildHlCombined(hlInputs.kb, hlInputs.init, hlInputs.goal, hlInputs.actions)}\n`;
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'hl_kb.pl';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);

        setHlGenerationStatus({
            type: 'success',
            message: 'Downloaded hl_kb.pl.',
        });
    };

    const runHlKbGeneration = async () => {
        if (!highLevelDesc.trim()) {
            setHlGenerationStatus({
                type: 'error',
                message: 'Please fill the high-level prompt before generating the HL KB.',
            });
            return;
        }

        setIsGeneratingHlKb(true);
        setHlGenerationStatus(null);

        try {
            const result = await generateHighLevelKB(
                highLevelDesc,
                selectedLlm,
                verifyHlGeneration ? verifyHlRetries : 0,
            );
            const kb = typeof result.kb === 'string' ? result.kb.trim() : '';
            const init = typeof result.init === 'string' ? result.init.trim() : '';
            const goal = typeof result.goal === 'string' ? result.goal.trim() : '';
            const actions = typeof result.actions === 'string' ? result.actions.trim() : '';

            if (!kb) {
                setHlGenerationStatus({
                    type: 'error',
                    message: 'The response did not contain a valid `kb` field.',
                });
                return;
            }

            setHlKbContent(kb);
            setHlInitContent(init);
            setHlGoalContent(goal);
            setHlActionsContent(actions);
            setHlCombinedContent(buildHlCombined(kb, init, goal, actions));

            const missingSections = [];
            if (!init) missingSections.push('init');
            if (!goal) missingSections.push('goal');
            if (!actions) missingSections.push('actions');

            setHlGenerationStatus({
                type: missingSections.length === 0 ? 'success' : 'error',
                message:
                    missingSections.length === 0
                        ? 'High-level KB generated (kb/init/goal/actions).'
                        : `Generated HL KB is incomplete. Missing sections: ${missingSections.join(', ')}.`,
            });
        } catch (error) {
            setHlGenerationStatus({
                type: 'error',
                message: error.message || 'HL KB generation failed.',
            });
        } finally {
            setIsGeneratingHlKb(false);
        }
    };

    const runLlKbGeneration = async () => {
        if (!lowLevelDesc.trim()) {
            setLlGenerationStatus({
                type: 'error',
                message: 'Please fill the low-level prompt before generating the LL KB.',
            });
            return;
        }

        const hlInputs = getHlInputsForLlGeneration({
            hlCombinedView,
            hlCombinedContent,
            hlKbContent,
            hlInitContent,
            hlGoalContent,
            hlActionsContent,
        });

        const missingHlInput = [];
        if (!hlInputs.kb.trim()) missingHlInput.push('kb');
        if (!hlInputs.init.trim()) missingHlInput.push('init');
        if (!hlInputs.goal.trim()) missingHlInput.push('goal');
        if (!hlInputs.actions.trim()) missingHlInput.push('actions');

        if (missingHlInput.length > 0) {
            setLlGenerationStatus({
                type: 'error',
                message: `HL input is incomplete. Please provide: ${missingHlInput.join(', ')}.`,
            });
            return;
        }

        setIsGeneratingLlKb(true);
        setLlGenerationStatus(null);

        try {
            const result = await generateLowLevelKB(
                lowLevelDesc,
                hlInputs.kb,
                hlInputs.init,
                hlInputs.goal,
                hlInputs.actions,
                selectedLlm,
                verifyLlGeneration ? verifyLlRetries : 0,
            );

            const kb = typeof result.kb === 'string' ? result.kb.trim() : '';
            const init = typeof result.init === 'string' ? result.init.trim() : '';
            const goal = typeof result.goal === 'string' ? result.goal.trim() : '';
            const actions =
                typeof result.ll_actions === 'string'
                    ? result.ll_actions.trim()
                    : (typeof result.actions === 'string' ? result.actions.trim() : '');
            const mappings = typeof result.mappings === 'string' ? result.mappings.trim() : '';

            if (!kb) {
                setLlGenerationStatus({
                    type: 'error',
                    message: 'The response did not contain a valid LL `kb` field.',
                });
                return;
            }

            setLlKbContent(kb);
            setLlInitContent(init);
            setLlGoalContent(goal);
            setLlActionsContent(actions);
            setLlMappingsContent(mappings);
            setLlCombinedContent(buildLlCombined(kb, init, goal, actions, mappings));

            const missingSections = [];
            if (!init) missingSections.push('init');
            if (!goal) missingSections.push('goal');
            if (!actions) missingSections.push('ll_actions');
            if (!mappings) missingSections.push('mappings');

            setLlGenerationStatus({
                type: missingSections.length === 0 ? 'success' : 'error',
                message:
                    missingSections.length === 0
                        ? 'Low-level KB generated (kb/init/goal/ll_actions/mappings).'
                        : `Generated LL KB is incomplete. Missing sections: ${missingSections.join(', ')}.`,
            });
        } catch (error) {
            setLlGenerationStatus({
                type: 'error',
                message: error.message || 'LL KB generation failed.',
            });
        } finally {
            setIsGeneratingLlKb(false);
        }
    };

    const runHlPlanGeneration = async (enableGraphDebug = false) => {
        const hlInputs = getHlInputsForLlGeneration({
            hlCombinedView,
            hlCombinedContent,
            hlKbContent,
            hlInitContent,
            hlGoalContent,
            hlActionsContent,
        });

        const llInputs = getLlInputsForExport({
            llCombinedView,
            llCombinedContent,
            llKbContent,
            llInitContent,
            llGoalContent,
            llActionsContent,
            llMappingsContent,
        });

        const missing = [];
        if (!hlInputs.actions.trim()) missing.push('HL actions');
        if (!llInputs.kb.trim()) missing.push('LL kb');
        if (!llInputs.init.trim()) missing.push('LL init');
        if (!llInputs.goal.trim()) missing.push('LL goal');
        if (!llInputs.llActions.trim()) missing.push('LL actions');
        if (!llInputs.mappings.trim()) missing.push('LL mappings');

        if (missing.length > 0) {
            setHlPlanStatus({
                type: 'error',
                message: `Cannot run planning. Missing sections: ${missing.join(', ')}.`,
            });
            return;
        }

        setIsGeneratingHlPlan(true);
        setHlPlanStatus(null);
        setHlPlanFound(false);
        if (!enableGraphDebug) {
            setHlPlanHtml('');
            setHlPlanUrl('');
        }
        setEnablersHtml('');
        setEnablersUrl('');
        setEnablerTerms([]);
        setPlanWithEnablers([]);
        setOptimizedStnStatus(null);
        setOptimizedStnGenerated(false);
        setOptimizedStnHtml('');
        setOptimizedStnUrl('');
        setOptimizedStnExecutionGraphHtml('');
        setOptimizedStnExecutionGraphUrl('');
        setOptimizedStnLog('');
        setBtStatus(null);
        setBtHtml('');
        setBtUrl('');
        setBtXml('');
        setBtXmlUrl('');
        setBtLog('');

        try {
            const result = await generateHighLevelPlanVisualization(
                hlInputs.actions,
                llInputs.kb,
                llInputs.init,
                llInputs.goal,
                llInputs.llActions,
                llInputs.mappings,
                parsePlannerInteger(planningMaxDepth, 10, -1),
                parsePlannerInteger(planningTimeoutSeconds, 180, 1),
                enableGraphDebug,
            );

            const html = typeof result.visualization_html === 'string' ? result.visualization_html : '';
            const log = typeof result.plan_log === 'string' ? result.plan_log : '';
            const steps = Array.isArray(result.plan_steps) ? result.plan_steps : [];
            const llPlanSteps = Array.isArray(result.ll_plan_steps) ? result.ll_plan_steps : [];
            const warning = typeof result.plan_warning === 'string' ? result.plan_warning : '';
            const mappingFailed = Boolean(result.mapping_failed);
            const planFound = Boolean(result.plan_found);
            const runId = typeof result.visualization_run_id === 'string' ? result.visualization_run_id : '';
            const visualizationUrl = typeof result.visualization_url === 'string' ? result.visualization_url : '';
            const enablersVisualizationHtml = typeof result.enablers_visualization_html === 'string'
                ? result.enablers_visualization_html
                : '';
            const enablersVisualizationUrl = typeof result.enablers_visualization_url === 'string'
                ? result.enablers_visualization_url
                : '';
            const enablers = Array.isArray(result.enabler_terms) ? result.enabler_terms : [];
            const parsedPlanWithEnablers = Array.isArray(result.plan_with_enablers)
                ? result.plan_with_enablers
                : [];

            if (mappingFailed) {
                setHlPlanLog(log);
                setHlPlanStatus({
                    type: 'error',
                    message: 'Problem in applying the mappings. Please check the errors and fix the knowledge-base.',
                });
                return;
            }

            if (html.trim()) {
                setHlPlanHtml(html);
                setHlPlanUrl(
                    visualizationUrl
                        ? `${apiBaseUrl.replace(/\/api$/, '')}${visualizationUrl}`
                        : (runId ? `${apiBaseUrl}/hl_plan_viz/${runId}` : ''),
                );
            }
            setHlPlanLog(log);
            setHlPlanSteps(steps);
            setToPlanSteps(llPlanSteps);
            setEnablersHtml(enablersVisualizationHtml);
            setEnablersUrl(
                enablersVisualizationUrl
                    ? `${apiBaseUrl.replace(/\/api$/, '')}${enablersVisualizationUrl}`
                    : (runId ? `${apiBaseUrl}/hl_plan_enablers_viz/${runId}` : ''),
            );
            setEnablerTerms(enablers);
            setPlanWithEnablers(parsedPlanWithEnablers);
            setHlPlanFound(planFound);

            if (planFound) {
                setHlPlanStatus({
                    type: 'success',
                    message: 'Planning successful',
                });
            } else if (enableGraphDebug) {
                setHlPlanStatus({
                    type: html.trim() ? 'warning' : 'error',
                    message: html.trim()
                        ? 'Search debug generated.'
                        : (warning || 'No high-level total-order plan found. Search graph could not be generated.'),
                });
            } else {
                setHlPlanStatus({
                    type: 'no-plan',
                    message: 'No high-level total-order plan found. If you want to see the search graph, click here.',
                });
            }
        } catch (error) {
            setHlPlanStatus({
                type: 'error',
                message: error.message || 'High-level planning failed.',
            });
        } finally {
            setIsGeneratingHlPlan(false);
        }
    };

    const runHlSearchDebug = () => runHlPlanGeneration(true);

    const stopHlPlanGeneration = async () => {
        try {
            const result = await stopHighLevelPlanGeneration();
            setHlPlanStatus({
                type: result.stopped ? 'warning' : 'error',
                message: result.message || (result.stopped ? 'Planner stop requested.' : 'No planner search is currently running.'),
            });
        } catch (error) {
            setHlPlanStatus({
                type: 'error',
                message: error.message || 'Failed to stop planner.',
            });
        }
    };

    const runOptimizedStnGeneration = async () => {
        if (!hlPlanLog.trim()) {
            setOptimizedStnStatus({
                type: 'error',
                message: 'Run high-level planning before generating the optimized STN.',
            });
            return;
        }

        setIsGeneratingOptimizedStn(true);
        setOptimizedStnStatus(null);
        setOptimizedStnGenerated(false);
        setBtStatus(null);
        setBtHtml('');
        setBtUrl('');
        setBtXml('');
        setBtXmlUrl('');
        setBtLog('');

        try {
            const result = await generateOptimizedStnVisualization(hlPlanLog);
            const html = typeof result.optimized_stn_html === 'string' ? result.optimized_stn_html : '';
            const visualizationUrl = typeof result.optimized_stn_url === 'string' ? result.optimized_stn_url : '';
            const executionGraphHtml = typeof result.optimized_stn_execution_graph_html === 'string'
                ? result.optimized_stn_execution_graph_html
                : '';
            const executionGraphUrl = typeof result.optimized_stn_execution_graph_url === 'string'
                ? result.optimized_stn_execution_graph_url
                : '';
            const log = typeof result.optimized_stn_log === 'string' ? result.optimized_stn_log : '';
            const warning = typeof result.optimized_stn_warning === 'string' ? result.optimized_stn_warning : '';

            if (!html.trim()) {
                setOptimizedStnStatus({
                    type: 'error',
                    message: 'Optimized STN generation completed but no visualization HTML was returned.',
                });
                return;
            }

            setOptimizedStnHtml(html);
            setOptimizedStnUrl(
                visualizationUrl
                    ? `${apiBaseUrl.replace(/\/api$/, '')}${visualizationUrl}`
                    : '',
            );
            setOptimizedStnExecutionGraphHtml(executionGraphHtml);
            setOptimizedStnExecutionGraphUrl(
                executionGraphUrl
                    ? `${apiBaseUrl.replace(/\/api$/, '')}${executionGraphUrl}`
                    : '',
            );
            setOptimizedStnLog(log);
            setOptimizedStnGenerated(Boolean(result.optimized_stn_generated));
            setOptimizedStnStatus({
                type: result.optimized_stn_generated ? 'success' : 'warning',
                message: result.optimized_stn_generated
                    ? 'Optimized STN generated.'
                    : (warning || 'Optimized STN generation returned a debug view.'),
            });
        } catch (error) {
            setOptimizedStnStatus({
                type: 'error',
                message: error.message || 'Optimized STN generation failed.',
            });
        } finally {
            setIsGeneratingOptimizedStn(false);
        }
    };

    const runBtGeneration = async () => {
        if (!optimizedStnGenerated) {
            setBtStatus({
                type: 'error',
                message: 'Generate the optimized STN before extracting the behavior tree.',
            });
            return;
        }

        if (!hlPlanLog.trim()) {
            setBtStatus({
                type: 'error',
                message: 'Run high-level planning before extracting the behavior tree.',
            });
            return;
        }

        setIsGeneratingBt(true);
        setBtStatus(null);

        try {
            const result = await generateOptimizedBehaviorTree(hlPlanLog);
            const html = typeof result.bt_html === 'string' ? result.bt_html : '';
            const xml = typeof result.bt_xml === 'string' ? result.bt_xml : '';
            const visualizationUrl = typeof result.bt_url === 'string' ? result.bt_url : '';
            const xmlUrl = typeof result.bt_xml_url === 'string' ? result.bt_xml_url : '';
            const log = typeof result.bt_log === 'string' ? result.bt_log : '';
            const warning = typeof result.bt_warning === 'string' ? result.bt_warning : '';

            if (!html.trim()) {
                setBtStatus({
                    type: 'error',
                    message: 'Behavior tree extraction completed but no visualization HTML was returned.',
                });
                return;
            }

            setBtHtml(html);
            setBtXml(xml);
            setBtUrl(
                visualizationUrl
                    ? `${apiBaseUrl.replace(/\/api$/, '')}${visualizationUrl}`
                    : '',
            );
            setBtXmlUrl(
                xmlUrl
                    ? `${apiBaseUrl.replace(/\/api$/, '')}${xmlUrl}`
                    : '',
            );
            setBtLog(log);
            setBtStatus({
                type: result.bt_generated ? 'success' : 'warning',
                message: result.bt_generated
                    ? 'Behavior tree extracted.'
                    : (warning || 'Behavior tree extraction returned a debug view.'),
            });
        } catch (error) {
            setBtStatus({
                type: 'error',
                message: error.message || 'Behavior tree extraction failed.',
            });
        } finally {
            setIsGeneratingBt(false);
        }
    };

    useEffect(() => {
        const textareas = document.querySelectorAll('textarea.auto-resize');
        textareas.forEach((textarea) => autoResizeTextarea(textarea));
    }, [
        currentStep,
        hlCombinedView,
        hlKbContent,
        hlInitContent,
        hlGoalContent,
        hlActionsContent,
        hlCombinedContent,
        llCombinedView,
        llKbContent,
        llInitContent,
        llGoalContent,
        llActionsContent,
        llMappingsContent,
        llCombinedContent,
    ]);

    const promptStepProps = {
        currentStep,
        highLevelDesc,
        lowLevelDesc,
        onHighLevelChange: handleHighLevelDescChange,
        onLowLevelChange: handleLowLevelDescChange,
        llmConfigs,
        selectedLlm,
        onSelectLlm: setSelectedLlm,
        llmLoadError,
        isChecking,
        validationStatus,
        skipConsistencyCheck,
        onSkipChange: handleSkipConsistencyCheckChange,
        onRunCheck: runConsistencyCheck,
    };

    const kbGenerationStepProps = {
        currentStep,
        highLevelDesc,
        lowLevelDesc,
        onHighLevelChange: handleHighLevelDescChange,
        onLowLevelChange: handleLowLevelDescChange,
        llmConfigs,
        selectedLlm,
        onSelectLlm: setSelectedLlm,
        llmLoadError,
        onAutoResize: handleAutoResizeTextarea,
        MIN_VERIFY_RETRY_BUDGET,
        parseRetryBudget,
        isGeneratingHlKb,
        hlGenerationStatus,
        verifyHlGeneration,
        onVerifyHlChange: setVerifyHlGeneration,
        verifyHlRetries,
        onVerifyHlRetriesChange: setVerifyHlRetries,
        hlCombinedView,
        onHlCombinedToggle: handleHlCombinedToggle,
        hlCombinedContent,
        onHlCombinedChange: handleHlCombinedChange,
        hlKbContent,
        onHlKbChange: setHlKbContent,
        hlInitContent,
        onHlInitChange: setHlInitContent,
        hlGoalContent,
        onHlGoalChange: setHlGoalContent,
        hlActionsContent,
        onHlActionsChange: setHlActionsContent,
        onRunHlGeneration: runHlKbGeneration,
        onDownloadHlKb: downloadHlKb,
        isGeneratingLlKb,
        llGenerationStatus,
        verifyLlGeneration,
        onVerifyLlChange: setVerifyLlGeneration,
        verifyLlRetries,
        onVerifyLlRetriesChange: setVerifyLlRetries,
        skipLlGeneration,
        onSkipLlGenerationChange: setSkipLlGeneration,
        llCombinedView,
        onLlCombinedToggle: handleLlCombinedToggle,
        llCombinedContent,
        onLlCombinedChange: handleLlCombinedChange,
        llKbContent,
        onLlKbChange: setLlKbContent,
        llInitContent,
        onLlInitChange: setLlInitContent,
        llGoalContent,
        onLlGoalChange: setLlGoalContent,
        llActionsContent,
        onLlActionsChange: setLlActionsContent,
        llMappingsContent,
        onLlMappingsChange: setLlMappingsContent,
        onRunLlGeneration: runLlKbGeneration,
        onDownloadLlKb: downloadLlKbWithHlActions,
    };

    const planningStepProps = {
        currentStep,
        isGeneratingHlPlan,
        hlPlanStatus,
        hlPlanFound,
        planningMaxDepth,
        onPlanningMaxDepthChange: setPlanningMaxDepth,
        planningTimeoutSeconds,
        onPlanningTimeoutSecondsChange: setPlanningTimeoutSeconds,
        hlPlanHtml,
        hlPlanUrl,
        hlPlanLog,
        hlPlanSteps,
        toPlanSteps,
        onRunHlPlanGeneration: () => runHlPlanGeneration(false),
        onRunHlSearchDebug: runHlSearchDebug,
        onStopHlPlanGeneration: stopHlPlanGeneration,
    };

    const enablersStepProps = {
        enablersHtml,
        enablersUrl,
        enablerTerms,
        planWithEnablers,
        hlPlanLog,
    };

    const optimizedStnStepProps = {
        isGeneratingOptimizedStn,
        optimizedStnStatus,
        optimizedStnHtml,
        optimizedStnUrl,
        optimizedStnExecutionGraphHtml,
        optimizedStnExecutionGraphUrl,
        optimizedStnLog,
        onRunOptimizedStnGeneration: runOptimizedStnGeneration,
    };

    const btStepProps = {
        isGeneratingBt,
        btStatus,
        btHtml,
        btUrl,
        btXml,
        btXmlUrl,
        btLog,
        onRunBtGeneration: runBtGeneration,
    };

    const stepName = STEPS[currentStep];
    const canProceedCurrentStep = canProceedFromStep(currentStep);

    return {
        steps: STEPS,
        currentStep,
        stepName,
        progress,
        canProceedCurrentStep,
        canAccessStep,
        goToStep,
        moveStep,
        promptStepProps,
        kbGenerationStepProps,
        planningStepProps,
        enablersStepProps,
        optimizedStnStepProps,
        btStepProps,
    };
};

export default useWorkflowController;

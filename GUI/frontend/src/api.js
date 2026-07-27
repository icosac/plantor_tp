// api.js

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000/api';

/**
 * Validate high-level and low-level descriptions.
 * @param {string} highLevel - High-level description text.
 * @param {string} lowLevel - Low-level description text.
 * @returns {Promise<Object>} API response.
 */
export const validateDescriptions = async (highLevel, lowLevel, llmConfig = '') => {
    const response = await fetch(`${API_BASE_URL}/validate`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            "Access-Control-Allow-Origin": "*"
        },
        body: JSON.stringify({ highLevel: highLevel, lowLevel: lowLevel, llmConfig: llmConfig }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error);
    }

    return response.json();
};

/**
 * List available LLM config files.
 * @returns {Promise<Object>} API response.
 */
export const listLlmConfigs = async () => {
    const response = await fetch(`${API_BASE_URL}/llm_configs`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error);
    }

    return response.json();
};

/**
 * Generate the high-level knowledge base.
 * @param {string} highLevel - High-level description text.
 * @returns {Promise<Object>} API response.
 */
export const generateHighLevelKB = async (highLevelDesc, llmConfig = '', verify = 0) => {
    const response = await fetch(`${API_BASE_URL}/generate_hl_kb`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: highLevelDesc, llmConfig: llmConfig, verify: verify }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error);
    }

    return response.json();
};

/**
 * Generate the low-level knowledge base.
 * @param {string} lowLevel - Low-level description text.
 * @returns {Promise<Object>} API response.
 */
export const generateLowLevelKB = async (
    lowLevelDesc,
    hlkbContent,
    hlInitContent,
    hlGoalContent,
    hlActionsContent,
    llmConfig = '',
    verify = 0,
) => {
    const response = await fetch(`${API_BASE_URL}/generate_ll_kb`, {
        method: 'POST',
        // mode: 'cors',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            lowLevelDesc: lowLevelDesc,
            hlkbContent: hlkbContent,
            hlInitContent: hlInitContent,
            hlGoalContent: hlGoalContent,
            hlActionsContent: hlActionsContent,
            llmConfig: llmConfig,
            verify: verify,
        }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error);
    }

    return response.json();
};


/**
 * Generate the behavior tree in XML format.
 * @param {string} lowLevelKB - Low-level knowledge base.
 * @returns {Promise<Object>} API response.
 */
export const generateBehaviorTree = async (lowLevelKB, lowLevelInit, lowLevelGoal, lowLevelActions, lowLevelMappings) => {
    const response = await fetch(`${API_BASE_URL}/generate_bt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            low_level_kb: lowLevelKB,
            low_level_init: lowLevelInit,
            low_level_goal: lowLevelGoal,
            low_level_actions: lowLevelActions,
            low_level_mappings: lowLevelMappings
        }),
    });

    if (!response.ok) {
        const error = await response.json();
        console.log("Something went wrong in generateBehaviorTree");
        throw new Error(error.error);
    }

    const data = response.json();

    console.log("data: ", data);

    return data;
};

/**
 * Generate the high-level total-order plan visualization (HTML).
 * @param {string} hlActions - High-level actions section.
 * @param {string} lowLevelKB - Low-level kb section.
 * @param {string} lowLevelInit - Low-level init section.
 * @param {string} lowLevelGoal - Low-level goal section.
 * @param {string} lowLevelActions - Low-level actions section.
 * @param {string} lowLevelMappings - Low-level mappings section.
 * @returns {Promise<Object>} API response.
 */
export const generateHighLevelPlanVisualization = async (
    hlActions,
    lowLevelKB,
    lowLevelInit,
    lowLevelGoal,
    lowLevelActions,
    lowLevelMappings,
    maxDepth = 10,
    timeoutSeconds = 180,
    enableGraphDebug = false,
) => {
    const response = await fetch(`${API_BASE_URL}/generate_hl_plan_viz`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            hl_actions: hlActions,
            low_level_kb: lowLevelKB,
            low_level_init: lowLevelInit,
            low_level_goal: lowLevelGoal,
            low_level_actions: lowLevelActions,
            low_level_mappings: lowLevelMappings,
            max_depth: maxDepth,
            timeout_seconds: timeoutSeconds,
            enable_graph_debug: enableGraphDebug,
        }),
    });

    if (!response.ok) {
        const error = await response.json();
        const detailsMessage = error?.details?.visualization_log || error?.details?.plan_error;
        const message = detailsMessage || error.error || 'High-level planning failed.';
        throw new Error(message);
    }

    return response.json();
};

/**
 * Stop the active high-level total-order planner process.
 * @returns {Promise<Object>} API response.
 */
export const stopHighLevelPlanGeneration = async () => {
    const response = await fetch(`${API_BASE_URL}/stop_hl_plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    });

    if (!response.ok) {
        const error = await response.json();
        const message = error.error || 'Failed to stop planner.';
        throw new Error(message);
    }

    return response.json();
};

/**
 * Generate the optimized STN visualization (HTML) from a planner log.
 * @param {string} planLog - Log returned by high-level total-order planning.
 * @returns {Promise<Object>} API response.
 */
export const generateOptimizedStnVisualization = async (planLog) => {
    const response = await fetch(`${API_BASE_URL}/generate_optimized_stn_viz`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            plan_log: planLog,
        }),
    });

    if (!response.ok) {
        const error = await response.json();
        const message = error.error || 'Optimized STN generation failed.';
        throw new Error(message);
    }

    return response.json();
};

/**
 * Generate behavior-tree XML and HTML from the optimized STN pipeline.
 * @param {string} planLog - Log returned by high-level total-order planning.
 * @returns {Promise<Object>} API response.
 */
export const generateOptimizedBehaviorTree = async (planLog) => {
    const response = await fetch(`${API_BASE_URL}/generate_optimized_bt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            plan_log: planLog,
        }),
    });

    if (!response.ok) {
        const error = await response.json();
        const message = error.error || 'Behavior tree extraction failed.';
        throw new Error(message);
    }

    return response.json();
};

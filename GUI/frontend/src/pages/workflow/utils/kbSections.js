export const buildHlCombined = (kb, init, goal, actions) => {
    return [
        ['kb', kb],
        ['init', init],
        ['goal', goal],
        ['actions', actions],
    ]
        .map(([name, value]) => `%%%%%%%%%%%%%%%%%%%%%%%\n% ${name}\n%%%%%%%%%%%%%%%%%%%%%%%\n${value || ''}`)
        .join('\n\n');
};

export const parseHlCombined = (text) => {
    const parsed = {
        kb: null,
        init: null,
        goal: null,
        actions: null,
    };

    const legacyPattern = /%%%%%%%%%%%%%%%%%%%%%%%\s*[\r\n]+%\s*(kb|init|goal|actions)\s*[\r\n]+%%%%%%%%%%%%%%%%%%%%%%%\s*[\r\n]+([\s\S]*?)(?=%%%%%%%%%%%%%%%%%%%%%%%\s*[\r\n]+%\s*(?:kb|init|goal|actions)\s*[\r\n]+%%%%%%%%%%%%%%%%%%%%%%%|$)/gi;
    let match = legacyPattern.exec(text);
    while (match) {
        parsed[match[1].toLowerCase()] = match[2].trim();
        match = legacyPattern.exec(text);
    }

    const markdownPattern = /```(kb|init|goal|actions)\s*([\s\S]*?)```/gi;
    match = markdownPattern.exec(text);
    while (match) {
        if (parsed[match[1].toLowerCase()] === null) {
            parsed[match[1].toLowerCase()] = match[2].trim();
        }
        match = markdownPattern.exec(text);
    }

    return parsed;
};

export const buildLlCombined = (kb, init, goal, llActions, mappings) => {
    return [
        ['kb', kb],
        ['init', init],
        ['goal', goal],
        ['ll_actions', llActions],
        ['mappings', mappings],
    ]
        .map(([name, value]) => `%%%%%%%%%%%%%%%%%%%%%%%\n% ${name}\n%%%%%%%%%%%%%%%%%%%%%%%\n${value || ''}`)
        .join('\n\n');
};

export const parseLlCombined = (text) => {
    const parsed = {
        kb: null,
        init: null,
        goal: null,
        ll_actions: null,
        mappings: null,
    };

    const legacyPattern = /%%%%%%%%%%%%%%%%%%%%%%%\s*[\r\n]+%\s*(kb|init|goal|actions|ll_actions|mappings)\s*[\r\n]+%%%%%%%%%%%%%%%%%%%%%%%\s*[\r\n]+([\s\S]*?)(?=%%%%%%%%%%%%%%%%%%%%%%%\s*[\r\n]+%\s*(?:kb|init|goal|actions|ll_actions|mappings)\s*[\r\n]+%%%%%%%%%%%%%%%%%%%%%%%|$)/gi;
    let match = legacyPattern.exec(text);
    while (match) {
        const section = match[1].toLowerCase() === 'actions' ? 'll_actions' : match[1].toLowerCase();
        parsed[section] = match[2].trim();
        match = legacyPattern.exec(text);
    }

    const markdownPattern = /```(kb|init|goal|actions|ll_actions|mappings)\s*([\s\S]*?)```/gi;
    match = markdownPattern.exec(text);
    while (match) {
        const section = match[1].toLowerCase() === 'actions' ? 'll_actions' : match[1].toLowerCase();
        if (parsed[section] === null) {
            parsed[section] = match[2].trim();
        }
        match = markdownPattern.exec(text);
    }

    return parsed;
};

export const getHlInputsForLlGeneration = ({
    hlCombinedView,
    hlCombinedContent,
    hlKbContent,
    hlInitContent,
    hlGoalContent,
    hlActionsContent,
}) => {
    if (hlCombinedView) {
        const parsed = parseHlCombined(hlCombinedContent || '');
        // In combined mode, use only what is currently present in the combined textarea.
        // Missing sections must be treated as empty (not silently fallback to stale per-section state).
        return {
            kb: parsed.kb ?? '',
            init: parsed.init ?? '',
            goal: parsed.goal ?? '',
            actions: parsed.actions ?? '',
        };
    }

    return {
        kb: hlKbContent,
        init: hlInitContent,
        goal: hlGoalContent,
        actions: hlActionsContent,
    };
};

export const getLlInputsForExport = ({
    llCombinedView,
    llCombinedContent,
    llKbContent,
    llInitContent,
    llGoalContent,
    llActionsContent,
    llMappingsContent,
}) => {
    if (llCombinedView) {
        const parsed = parseLlCombined(llCombinedContent || '');
        // In combined mode, do not fallback to previous values if parsing fails.
        // This guarantees that what the user typed is what gets validated/exported.
        return {
            kb: parsed.kb ?? '',
            init: parsed.init ?? '',
            goal: parsed.goal ?? '',
            llActions: parsed.ll_actions ?? '',
            mappings: parsed.mappings ?? '',
        };
    }

    return {
        kb: llKbContent,
        init: llInitContent,
        goal: llGoalContent,
        llActions: llActionsContent,
        mappings: llMappingsContent,
    };
};

export const buildLlExportWithHlActions = (hlActions, llInputs) => {
    return [
        ['actions', hlActions],
        ['kb', llInputs.kb],
        ['init', llInputs.init],
        ['goal', llInputs.goal],
        ['ll_actions', llInputs.llActions],
        ['mappings', llInputs.mappings],
    ]
        .map(([name, value]) => `%%%%%%%%%%%%%%%%%%%%%%%\n% ${name}\n%%%%%%%%%%%%%%%%%%%%%%%\n${value || ''}`)
        .join('\n\n');
};

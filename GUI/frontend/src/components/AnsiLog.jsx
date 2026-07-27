import React from 'react';

const ANSI_PATTERN = /\x1b\[([0-9;]*)m/g;

const ANSI_COLORS = {
    30: '#343a40',
    31: '#c92a2a',
    32: '#2b8a3e',
    33: '#e67700',
    34: '#1864ab',
    35: '#9c36b5',
    36: '#0b7285',
    37: '#f8f9fa',
    90: '#868e96',
    91: '#e03131',
    92: '#37b24d',
    93: '#f08c00',
    94: '#1c7ed6',
    95: '#ae3ec9',
    96: '#1098ad',
    97: '#ffffff',
};

const emptyStyle = () => ({
    color: null,
    backgroundColor: null,
    fontWeight: null,
});

const isStyled = (style) => (
    Boolean(style.color || style.backgroundColor || style.fontWeight)
);

const toSpanStyle = (style) => {
    const spanStyle = {};
    if (style.color) spanStyle.color = style.color;
    if (style.backgroundColor) spanStyle.backgroundColor = style.backgroundColor;
    if (style.fontWeight) spanStyle.fontWeight = style.fontWeight;
    return spanStyle;
};

const applyAnsiCodes = (baseStyle, rawCodes) => {
    const style = { ...baseStyle };
    const codes = rawCodes.length === 0
        ? [0]
        : rawCodes
            .split(';')
            .map((code) => Number.parseInt(code, 10))
            .filter((code) => Number.isInteger(code));

    codes.forEach((code) => {
        if (code === 0) {
            Object.assign(style, emptyStyle());
        } else if (code === 1) {
            style.fontWeight = 700;
        } else if (code === 22) {
            style.fontWeight = null;
        } else if (code === 39) {
            style.color = null;
        } else if (code === 49) {
            style.backgroundColor = null;
        } else if (ANSI_COLORS[code]) {
            style.color = ANSI_COLORS[code];
        } else if (code >= 40 && code <= 47) {
            style.backgroundColor = ANSI_COLORS[code - 10];
        } else if (code >= 100 && code <= 107) {
            style.backgroundColor = ANSI_COLORS[code - 10];
        }
    });

    return style;
};

const renderAnsiText = (text) => {
    const value = String(text || '');
    const parts = [];
    let style = emptyStyle();
    let lastIndex = 0;
    let match;

    ANSI_PATTERN.lastIndex = 0;
    while ((match = ANSI_PATTERN.exec(value)) !== null) {
        if (match.index > lastIndex) {
            const chunk = value.slice(lastIndex, match.index);
            parts.push({ text: chunk, style: { ...style } });
        }
        style = applyAnsiCodes(style, match[1]);
        lastIndex = ANSI_PATTERN.lastIndex;
    }

    if (lastIndex < value.length) {
        parts.push({ text: value.slice(lastIndex), style: { ...style } });
    }

    return parts.map((part, index) => {
        if (!isStyled(part.style)) {
            return <React.Fragment key={index}>{part.text}</React.Fragment>;
        }
        return (
            <span key={index} style={toSpanStyle(part.style)}>
                {part.text}
            </span>
        );
    });
};

const AnsiLog = ({ text, className = '' }) => (
    <pre className={className}>{renderAnsiText(text)}</pre>
);

export default AnsiLog;

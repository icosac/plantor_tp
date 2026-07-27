// GeneratedCodeView.jsx

import React from 'react';
import PropTypes from 'prop-types';

const GeneratedCodeView = ({ title, code, onEdit }) => {
    return (
        <div className="mb-6">
            <h3 className="text-lg font-bold mb-2">{title}</h3>
            <textarea
                className="w-full p-2 border rounded bg-gray-100 focus:outline-none focus:ring focus:border-blue-300"
                rows="10"
                value={code}
                onChange={(e) => onEdit(e.target.value)}
            />
        </div>
    );
};

GeneratedCodeView.propTypes = {
    title: PropTypes.string.isRequired,
    code: PropTypes.string.isRequired,
    onEdit: PropTypes.func.isRequired,
};

export default GeneratedCodeView;

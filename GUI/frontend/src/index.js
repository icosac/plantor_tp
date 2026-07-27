import React from 'react';
import ReactDOM from 'react-dom/client'; // Use this for React 18+ (ReactDOM.createRoot)
// import './index.css'; // Your global CSS styles
import App from './App'; // Import the main App component

// Create the root and render the App component
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
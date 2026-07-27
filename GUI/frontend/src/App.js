// App.js

import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import About from './pages/About';
import Help from './pages/Help';

function App() {
    return (
        <Router>
            <div className="App">
                <Navbar />
                <main className="container mt-4">
                    <Routes>
                        <Route path="/" element={<Home />} />
                        <Route path="/about" element={<About />} />
                        <Route path="/help" element={<Help />} />
                    </Routes>
                </main>
            </div>
        </Router>
    );
}

export default App;

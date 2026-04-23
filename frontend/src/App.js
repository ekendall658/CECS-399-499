import React, { useState } from 'react';
import axios from 'axios';
import Plot from 'react-plotly.js';

/**
 * PROJECT: From Ingestion to Interaction: An Automated Data Pipeline for Intelligent Energy Consumption Analysis
 */

function App() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  /**
   * handleSearch
   * Sends user query to the backend and sanitizes AI formatting artifacts.
   */
  const handleSearch = async () => {
    if (!question.trim()) return;
    setLoading(true);
    
    try {
      const response = await axios.post('http://localhost:8000/chat/', {
        question: question
      });
      
      let data = response.data;
      
      /**
       * DATA CLEANING:
       * Strips Markdown backticks (```) from the intent if the AI includes them.
       */
      if (data.intent && typeof data.intent === 'string') {
        data.intent = data.intent.replace(/```json|```/g, "").trim();
      }
      
      setResult(data);
    } catch (error) {
      console.error("Connection Error:", error);
      alert("Error: The backend server is not responding. Please check if FastAPI is running.");
    } finally {
      setLoading(false);
    }
  };

  const styles = {
    container: {
      maxWidth: '850px',
      margin: '0 auto',
      padding: '80px 20px',
      fontFamily: '"Inter", -apple-system, sans-serif',
      color: '#111'
    },
    header: {
      textAlign: 'center',
      marginBottom: '60px'
    },
    title: {
      fontSize: '28px',
      fontWeight: '800',
      marginBottom: '10px',
      lineHeight: '1.2'
    },
    subtitle: {
      fontSize: '16px',
      color: '#666',
      fontWeight: '400'
    },
    searchBox: {
      display: 'flex',
      gap: '12px',
      marginBottom: '50px'
    },
    input: {
      flex: 1,
      padding: '15px 20px',
      borderRadius: '10px',
      border: '1px solid #ddd',
      fontSize: '16px',
      outline: 'none'
    },
    button: {
      padding: '0 30px',
      borderRadius: '10px',
      backgroundColor: '#000',
      color: '#fff',
      border: 'none',
      cursor: 'pointer',
      fontWeight: 'bold',
      fontSize: '15px'
    },
    resultCard: {
      padding: '30px',
      borderRadius: '16px',
      backgroundColor: '#f9f9f9',
      border: '1px solid #efefef'
    },
    intent: {
      fontSize: '12px',
      color: '#888',
      textTransform: 'uppercase',
      letterSpacing: '1px',
      display: 'block',
      marginBottom: '15px'
    },
    answer: {
      fontSize: '18px',
      lineHeight: '1.7',
      margin: '0 0 30px 0'
    }
  };

  return (
    <div style={styles.container}>
      {/* 1. Project Title Section */}
      <header style={styles.header}>
        <h1 style={styles.title}>From Ingestion to Interaction</h1>
        <p style={styles.subtitle}>An Automated Data Pipeline for Intelligent Energy Consumption Analysis</p>
      </header>

      {/* 2. Interaction Section */}
      <div style={styles.searchBox}>
        <input 
          type="text" 
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Enter your energy analysis question..."
          style={styles.input}
        />
        <button 
          onClick={handleSearch} 
          disabled={loading}
          style={styles.button}
        >
          {loading ? 'Analyzing...' : 'Search'}
        </button>
      </div>

      {/* 3. Output Section */}
      {result && (
        <div style={styles.resultCard}>
          <span style={styles.intent}>Analysis Intent: {result.intent}</span>
          <p style={styles.answer}>{result.answer}</p>

          {/* Visualization - Only rendered if data exists */}
          {result.sql_result && result.sql_result.length > 0 && (
            <div style={{ marginTop: '30px', borderTop: '1px solid #ddd', paddingTop: '30px' }}>
              <Plot
                data={[{
                  x: result.sql_result.map(row => row.county || row.date || row.name),
                  y: result.sql_result.map(row => row.count || row.value || row.anomaly_count),
                  type: 'bar',
                  marker: { color: '#000' }
                }]}
                layout={{ 
                  autosize: true, 
                  title: 'Data Visualization',
                  font: { family: 'Inter, sans-serif' },
                  margin: { t: 50, b: 50, l: 50, r: 20 }
                }}
                useResizeHandler={true}
                style={{ width: "100%", height: "400px" }}
                config={{ displayModeBar: false }}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
import React, { useState } from 'react';
import {
  Container,
  TextField,
  Button,
  Paper,
  Typography,
  Box,
  CircularProgress,
} from '@mui/material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import axios from 'axios';

function App() {
  const [symbol, setSymbol] = useState('');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const handleAnalyze = async () => {
    if (!symbol) {
      setError('Please enter a stock symbol');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post('http://localhost:8000/analyze', {
        symbol: symbol.toUpperCase(),
        start_date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        end_date: new Date().toISOString().split('T')[0]
      });

      setData(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Paper elevation={3} sx={{ p: 3, mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Stock Support/Resistance Analyzer
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
          <TextField
            label="Stock Symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="e.g., AAPL"
            fullWidth
          />
          <Button
            variant="contained"
            onClick={handleAnalyze}
            disabled={loading}
            sx={{ minWidth: 120 }}
          >
            {loading ? <CircularProgress size={24} /> : 'Analyze'}
          </Button>
        </Box>

        {error && (
          <Typography color="error" sx={{ mb: 2 }}>
            {error}
          </Typography>
        )}

        {data && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Support Levels:
            </Typography>
            <Typography sx={{ mb: 2 }}>
              {data.support_levels.map((level, i) => (
                <span key={i} style={{ marginRight: '1rem' }}>
                  ${level.toFixed(2)}
                </span>
              ))}
            </Typography>

            <Typography variant="h6" gutterBottom>
              Resistance Levels:
            </Typography>
            <Typography>
              {data.resistance_levels.map((level, i) => (
                <span key={i} style={{ marginRight: '1rem' }}>
                  ${level.toFixed(2)}
                </span>
              ))}
            </Typography>
          </Box>
        )}
      </Paper>
    </Container>
  );
}

export default App; 
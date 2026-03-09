import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import axios from 'axios';

import config from '../config';

const Home = () => {
  const [waterLevel, setWaterLevel] = useState(0);
  const [temperature, setTemperature] = useState(0);
  const [waterLevelData, setWaterLevelData] = useState([]);
  const [temperatureData, setTemperatureData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [selectedNode, setSelectedNode] = useState('');
  const [hasDataForNode, setHasDataForNode] = useState(true);
  const [nodeDataMessage, setNodeDataMessage] = useState('');
  const [selectedTimeRange, setSelectedTimeRange] = useState('all');
  const [customFromDate, setCustomFromDate] = useState('');
  const [customToDate, setCustomToDate] = useState('');

  // Mapping between node IDs and tank IDs for sensor data
  const getActualTankId = (nodeId) => {
    const mapping = {
      'Node 1': 'NODE_001',
      'Node 2': 'NODE_002', // Add if needed
      'string': '1', // Maps to ID "1" in sensor data
      'NODE_001': 'NODE_001' // Direct mapping
    };
    return mapping[nodeId] || nodeId;
  };

  // Get time range parameters based on selection
  const getTimeRangeParams = () => {
    const now = new Date();
    let fromDate, toDate;

    switch (selectedTimeRange) {
      case '1h':
        fromDate = new Date(now.getTime() - (1 * 60 * 60 * 1000));
        toDate = now;
        break;
      case '6h':
        fromDate = new Date(now.getTime() - (6 * 60 * 60 * 1000));
        toDate = now;
        break;
      case '24h':
        fromDate = new Date(now.getTime() - (24 * 60 * 60 * 1000));
        toDate = now;
        break;
      case '7d':
        fromDate = new Date(now.getTime() - (7 * 24 * 60 * 60 * 1000));
        toDate = now;
        break;
      case 'custom':
        if (customFromDate && customToDate) {
          fromDate = new Date(customFromDate);
          toDate = new Date(customToDate);
        } else {
          return null; // No custom dates set
        }
        break;
      default:
        fromDate = new Date(now.getTime() - (24 * 60 * 60 * 1000));
        toDate = now;
    }

    return {
      from: fromDate.toISOString(),
      to: toDate.toISOString()
    };
  };

  // Fetch real sensor data from API
  const fetchSensorData = async () => {
    try {
      setLoading(true);
      // Add tank_id parameter if a node is selected
      // Map the selected node to actual tank_id used in sensor data
      const actualTankId = selectedNode ? getActualTankId(selectedNode) : null;
      const timeParams = getTimeRangeParams();

      let url = config.SENSOR_DATA_URL;

      const response = await axios.get(url, {
        headers: {
          'accept': 'application/json'
        }
      });

      const allSensorData = response.data || [];

      const actualNodeId = getActualTankId(selectedNode);

      const sensorData = allSensorData.filter(
        (item) => item.node_id === actualNodeId
      );

      // Check if data exists for the selected node
      if (sensorData.length > 0) {
        setHasDataForNode(true);
        setNodeDataMessage('');
        // Get the latest reading for current values
        const latest = sensorData[0];

        // Get tank height for the selected node (default to 200cm if not found)
        const selectedNodeData = nodes.find(n => n.id === selectedNode);
        const tankHeight = selectedNodeData?.tank_height || 200;

        // Convert water level cm to percentage using actual tank height
        const waterLevelPercentage = Math.min(
          100,
          Math.round(((tankHeight - latest.distance) / tankHeight) * 100)
        );

        setWaterLevel(waterLevelPercentage);
        setTemperature(Math.round(latest.temperature * 10) / 10);
        setLastUpdated(new Date(latest.created_at));

        // Process data for charts (reverse to show chronological order)
        const reversedData = [...sensorData].reverse();

        const waterData = reversedData.map(item => {
          const time = new Date(item.created_at).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
          });
          // const percentage = Math.min(100, Math.round((item.water_level_cm / tankHeight) * 100 * 10) / 10);
          const percentage = Math.min(
            100,
            Math.round(((tankHeight - item.distance) / tankHeight) * 100)
          );
          return {
            time: time,
            value: percentage,
            raw_cm: item.distance
          };
        });

        const tempData = reversedData.map(item => {
          const time = new Date(item.created_at).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
          });

          return {
            time: time,
            value: Math.round(item.temperature * 10) / 10
          };
        });

        setWaterLevelData(waterData);
        setTemperatureData(tempData);
      } else {
        // No data found for selected node
        setHasDataForNode(false);
        if (selectedNode) {
          const actualTankId = getActualTankId(selectedNode);
          setNodeDataMessage(`No sensor data found for ${selectedNode} (checking tank_id: ${actualTankId})`);
        } else {
          setNodeDataMessage('No sensor data available');
        }
        // Reset values when no data
        setWaterLevel(0);
        setTemperature(0);
        setWaterLevelData([]);
        setTemperatureData([]);
        setLastUpdated(null);
      }
    } catch (error) {
      console.error('Error fetching sensor data:', error);
      setHasDataForNode(false);
      setNodeDataMessage('Error fetching sensor data. Please try again.');
      // Keep existing data or show error state
    } finally {
      setLoading(false);
    }
  };

  // Fetch available nodes from tank_sensorparameters table
  const fetchNodes = async () => {
    try {
      const response = await axios.get(
        config.TANK_PARAMETERS_URL,
        {
          headers: {
            'accept': 'application/json'
          }
        }
      );

      const nodesData = response.data || [];
      // Transform the data to match our node structure
      const transformedNodes = nodesData.map(node => ({
        id: node.node_id,
        name: node.node_id,
        tank_height: node.tank_height_cm,
        tank_length: node.tank_length_cm,
        tank_width: node.tank_width_cm,
        latitude: node.lat,
        longitude: node.long
      }));

      setNodes(transformedNodes);

      // Set first node as default if no node is selected
      if (transformedNodes.length > 0 && !selectedNode) {
        setSelectedNode(transformedNodes[0].id);
      }
    } catch (error) {
      console.error('Error fetching nodes:', error);
      // If API fails, create some sample nodes based on your data
      const sampleNodes = [
        { id: 'Node 1', name: 'Node 1', tank_height: 22, tank_length: 22, tank_width: 0.2 },
        { id: 'Node 2', name: 'Node 2', tank_height: 0.4, tank_length: 0.4, tank_width: 0.5 },
        { id: 'string', name: 'string', tank_height: 0, tank_length: 0, tank_width: 0 },
        { id: 'NODE_001', name: 'Tank 001', tank_height: 200, tank_length: 100, tank_width: 100 }
      ];
      setNodes(sampleNodes);
      if (!selectedNode) {
        setSelectedNode(sampleNodes[0].id);
      }
    }
  };

  // Handle node selection change
  const handleNodeChange = (event) => {
    const nodeId = event.target.value;
    setSelectedNode(nodeId);
    setNodeDataMessage(''); // Clear previous messages

    // Reset data state while loading
    if (nodeId) {
      setLoading(true);
      const actualTankId = getActualTankId(nodeId);
      setNodeDataMessage(`Checking data for ${nodeId} (tank_id: ${actualTankId})...`);
    }
  };

  // Handle time range selection change
  const handleTimeRangeChange = (event) => {
    const timeRange = event.target.value;
    setSelectedTimeRange(timeRange);

    // Clear custom dates if not selecting custom
    if (timeRange !== 'custom') {
      setCustomFromDate('');
      setCustomToDate('');
    }
  };

  // Handle custom date changes
  const handleCustomFromDateChange = (event) => {
    setCustomFromDate(event.target.value);
  };

  const handleCustomToDateChange = (event) => {
    setCustomToDate(event.target.value);
  };

  useEffect(() => {
    // Initial data fetch
    fetchNodes();
    fetchSensorData();

    // Update data every 30 seconds
    const interval = setInterval(() => {
      fetchSensorData();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  // Effect to refetch sensor data when selectedNode changes
  useEffect(() => {
    if (selectedNode) {
      fetchSensorData();
    }
  }, [selectedNode]);

  // Effect to refetch sensor data when time range changes
  useEffect(() => {
    if (selectedTimeRange && selectedNode) {
      fetchSensorData();
    }
  }, [selectedTimeRange]);

  // Effect to refetch sensor data when custom dates change
  useEffect(() => {
    if (selectedTimeRange === 'custom' && customFromDate && customToDate && selectedNode) {
      fetchSensorData();
    }
  }, [customFromDate, customToDate]);

  return (
    <div className="home-page">
      <div className="page-header">
        <div className="header-left">
          <h2 className="page-title">Dashboard Overview</h2>
          <div className="node-selector">
            <label htmlFor="node-select" className="node-label">Tank:</label>
            <select
              id="node-select"
              value={selectedNode}
              onChange={handleNodeChange}
              className="node-dropdown"
            >
              <option value="">Select Tank/Node</option>
              {nodes.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.id}
                  {node.tank_height > 0 && ` (${node.tank_height}cm tank)`}
                </option>
              ))}
            </select>
          </div>

          <div className="time-range-selector">
            <label htmlFor="time-range-select" className="time-range-label">Time Range:</label>
            <select
              id="time-range-select"
              value={selectedTimeRange}
              onChange={handleTimeRangeChange}
              className="time-range-dropdown"
            >
              <option value="all">All Time</option>
              <option value="1h">Last 1 Hour</option>
              <option value="6h">Last 6 Hours</option>
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="custom">Custom Range</option>
            </select>
          </div>

          {selectedTimeRange === 'custom' && (
            <div className="custom-date-range">
              <div className="date-input-group">
                <label htmlFor="from-date" className="date-label">From:</label>
                <input
                  id="from-date"
                  type="datetime-local"
                  value={customFromDate}
                  onChange={handleCustomFromDateChange}
                  className="date-input"
                />
              </div>
              <div className="date-input-group">
                <label htmlFor="to-date" className="date-label">To:</label>
                <input
                  id="to-date"
                  type="datetime-local"
                  value={customToDate}
                  onChange={handleCustomToDateChange}
                  className="date-input"
                />
              </div>
            </div>
          )}
        </div>
        {lastUpdated && (
          <div className="last-updated">
            Last updated: {lastUpdated.toLocaleTimeString('en-US', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit'
            })}
            {loading && <span className="update-indicator"> • Updating...</span>}
          </div>
        )}
      </div>

      {/* Data Status Message */}
      {nodeDataMessage && (
        <div className={`data-status-message ${hasDataForNode ? 'success' : 'warning'}`}>
          <div className="status-icon">
            {hasDataForNode ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="20,6 9,17 4,12"></polyline>
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
            )}
          </div>
          <span>{nodeDataMessage}</span>
        </div>
      )}

      {selectedNode && hasDataForNode && (
        <div className="selected-node-info">
          <strong>Showing data for node:</strong> {selectedNode}
          {getActualTankId(selectedNode) !== selectedNode && (
            <span className="tank-mapping"> → tank_id: {getActualTankId(selectedNode)}</span>
          )}
          <span className="time-range-info">
            {' '}• Time Range: {
              selectedTimeRange === '1h' ? 'Last 1 Hour' :
                selectedTimeRange === '6h' ? 'Last 6 Hours' :
                  selectedTimeRange === '24h' ? 'Last 24 Hours' :
                    selectedTimeRange === '7d' ? 'Last 7 Days' :
                      selectedTimeRange === 'all' ? 'All Time' :
                        selectedTimeRange === 'custom' ? 'Custom Range' : 'Last 24 Hours'
            }
          </span>
          {nodes.find(n => n.id === selectedNode)?.tank_height && (
            <span className="tank-specs">
              {' '}• Tank: {nodes.find(n => n.id === selectedNode)?.tank_height}cm (H) × {nodes.find(n => n.id === selectedNode)?.tank_length}cm (L) × {nodes.find(n => n.id === selectedNode)?.tank_width}cm (W)
            </span>
          )}
        </div>
      )}

      {/* Cards Section */}
      <div className="cards-container">
        <div className="card water-level-card">
          <div className="card-header">
            <div className="card-icon water-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2.69l5.66 5.66a8 8 0 11-11.31 0z" />
              </svg>
            </div>
            <h3>Water Level</h3>
          </div>
          <div className="card-value">
            <span className="value">
              {loading ? '--' : (!hasDataForNode ? 'N/A' : waterLevel)}
            </span>
            <span className="unit">%</span>
          </div>
          <div className="card-status">
            <span className={`status ${!hasDataForNode ? 'no-data' : waterLevel > 50 ? 'good' : 'warning'}`}>
              {!hasDataForNode ? 'No Data' :
                waterLevel > 80 ? 'High' : waterLevel > 50 ? 'Normal' : waterLevel > 20 ? 'Low' : 'Critical'}
            </span>
          </div>
        </div>

        <div className="card temperature-card">
          <div className="card-header">
            <div className="card-icon temp-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 4v10.54a4 4 0 11-4 0V4a2 2 0 114 0z" />
              </svg>
            </div>
            <h3>Temperature</h3>
          </div>
          <div className="card-value">
            <span className="value">
              {loading ? '--' : (!hasDataForNode ? 'N/A' : temperature)}
            </span>
            <span className="unit">°C</span>
          </div>
          <div className="card-status">
            <span className={`status ${!hasDataForNode ? 'no-data' : temperature < 30 ? 'good' : 'warning'}`}>
              {!hasDataForNode ? 'No Data' :
                temperature < 25 ? 'Normal' : temperature < 30 ? 'Warm' : 'Hot'}
            </span>
          </div>
        </div>
      </div>

      {/* Graphs Section */}
      <div className="graphs-container">
        <div className="graph-card">
          <h3>Water Level </h3>
          {loading && waterLevelData.length === 0 ? (
            <div className="graph-loading">Loading sensor data...</div>
          ) : !hasDataForNode ? (
            <div className="no-data-graph">
              <div className="no-data-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
              </div>
              <p>No data available for the selected node</p>
              <small>Please select a node with available sensor data</small>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={waterLevelData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis domain={[0, 100]} />
                <Tooltip
                  labelFormatter={(value) => `Time: ${value}`}
                  formatter={(value, name, props) => [
                    `${value}% (${props.payload.raw_cm}cm)`,
                    'Water Level'
                  ]}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#2196F3"
                  strokeWidth="3"
                  dot={{ fill: '#2196F3', strokeWidth: 2, r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="graph-card">
          <h3>Temperature </h3>
          {loading && temperatureData.length === 0 ? (
            <div className="graph-loading">Loading sensor data...</div>
          ) : !hasDataForNode ? (
            <div className="no-data-graph">
              <div className="no-data-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
              </div>
              <p>No data available for the selected node</p>
              <small>Please select a node with available sensor data</small>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={temperatureData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis domain={['dataMin - 2', 'dataMax + 2']} />
                <Tooltip
                  labelFormatter={(value) => `Time: ${value}`}
                  formatter={(value) => [`${value}°C`, 'Temperature']}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#FF9800"
                  strokeWidth="3"
                  dot={{ fill: '#FF9800', strokeWidth: 2, r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
};

export default Home;

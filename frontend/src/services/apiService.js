/**
 * API Service - Communicates with Flask backend
 */

import axios from 'axios';

const API_BASE_URL = 'http://localhost:5000/api';

class APIService {
  
  async getNetwork() {
    try {
      const response = await axios.get(`${API_BASE_URL}/network`);
      return response.data;
    } catch (error) {
      console.error('Error fetching network:', error);
      throw error;
    }
  }

  async getTrafficLights() {
    try {
      const response = await axios.get(`${API_BASE_URL}/traffic-lights`);
      return response.data;
    } catch (error) {
      console.error('Error fetching traffic lights:', error);
      throw error;
    }
  }

  async getHospitals() {
    try {
      const response = await axios.get(`${API_BASE_URL}/hospitals`);
      return response.data;
    } catch (error) {
      console.error('Error fetching hospitals:', error);
      throw error;
    }
  }

  async getRoutes(sourceId = null, destId = null) {
    try {
      let url = `${API_BASE_URL}/routes`;
      const params = new URLSearchParams();
      
      if (sourceId) params.append('source_id', sourceId);
      if (destId) params.append('dest_id', destId);
      
      if (params.toString()) {
        url += `?${params.toString()}`;
      }
      
      const response = await axios.get(url);
      return response.data;
    } catch (error) {
      console.error('Error fetching routes:', error);
      throw error;
    }
  }

  async getStats() {
    try {
      const response = await axios.get(`${API_BASE_URL}/stats`);
      return response.data;
    } catch (error) {
      console.error('Error fetching stats:', error);
      throw error;
    }
  }
}

export default new APIService();

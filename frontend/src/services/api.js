import axios from "axios";

const api = axios.create({
  baseURL:
    import.meta.env.VITE_API_URL ||
    "https://roadvision-api.up.railway.app/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("roadvision_token");

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

export default api;
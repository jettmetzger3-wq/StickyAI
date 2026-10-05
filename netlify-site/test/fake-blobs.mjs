// In-memory stand-in for @netlify/blobs, for the function test.
const data = new Map();
const store = {
  async get(key, opts) {
    if (!data.has(key)) return null;
    const v = data.get(key);
    return opts?.type === "json" ? JSON.parse(v) : v;
  },
  async setJSON(key, value) { data.set(key, JSON.stringify(value)); },
  async delete(key) { data.delete(key); },
};
export const getStore = () => store;
export const getDeployStore = () => store;

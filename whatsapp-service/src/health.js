import express from "express";
import { getClient } from "./client.js";

export function createHealthRouter() {
  const router = express.Router();
  router.get("/health", (_req, res) => {
    const ready = !!getClient();
    res.json({
      status: ready ? "ok" : "degraded",
      whatsapp: ready ? "connected" : "disconnected",
    });
  });
  return router;
}

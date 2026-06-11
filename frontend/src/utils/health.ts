type ServiceStatuses = Record<string, string>;

export function formatHealthStatus(services: ServiceStatuses) {
  const total = Object.keys(services).length;
  const healthy = Object.values(services).filter(s => s === 'ok').length;
  return { overall: healthy === total ? 'operational' : 'degraded', services: total, healthy };
}

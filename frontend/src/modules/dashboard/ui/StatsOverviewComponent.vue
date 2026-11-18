<template><div class="stats-overview-container"><DashboardMetricGrid>
  <DashboardMetricCard :icon="MessageCircle" :value="formatNumber(basicStats?.total_sessions)" label="累计研究会话" tone="primary" />
  <DashboardMetricCard :icon="Activity" :value="formatNumber(basicStats?.active_sessions)" label="未归档会话" tone="success" />
  <DashboardMetricCard :icon="Mail" :value="formatNumber(basicStats?.total_messages)" label="总消息数" tone="info" />
  <DashboardMetricCard :icon="Users" :value="formatNumber(basicStats?.total_users)" label="用户数" tone="warning" />
</DashboardMetricGrid></div></template>
<script setup>
import { MessageCircle, Activity, Mail, Users } from '@lucide/vue'
import { formatNumber } from '@/modules/dashboard/model/dashboard'
import DashboardMetricCard from './DashboardMetricCard.vue'
import DashboardMetricGrid from './DashboardMetricGrid.vue'
defineProps({ basicStats: { type: Object, default: () => ({}) } })
</script>
<style scoped>.stats-overview-container { margin-top:8px; } .dashboard-metric-grid { padding:0 var(--page-padding); grid-template-columns:repeat(4,minmax(0,1fr)); } @media(max-width:1024px) { .dashboard-metric-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }</style>

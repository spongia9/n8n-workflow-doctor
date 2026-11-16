import { createRouter, createWebHistory } from 'vue-router'
export const router = createRouter({
  history: createWebHistory(), routes: [
    { path: '/', component: () => import('../views/Dashboard.vue'), meta: { title: '工作台' } },
    { path: '/upload', component: () => import('../views/Upload.vue'), meta: { title: '上传与扫描' } },
    { path: '/scans/:id', component: () => import('../views/Results.vue'), meta: { title: '诊断结果' } },
    { path: '/scans/:id/graph', component: () => import('../views/Graphs.vue'), meta: { title: '依赖可视化' } },
    { path: '/scans/:id/reports', component: () => import('../views/Reports.vue'), meta: { title: '报告中心' } },
    { path: '/:pathMatch(.*)*', component: () => import('../views/NotFound.vue'), meta: { title: '页面不存在' } },
  ],
})

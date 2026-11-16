import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { ElButton, ElConfigProvider, ElPagination } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/pagination/style/css'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './styles/main.css'
import App from './App.vue'
import { router } from './router'
createApp({ render: () => h(ElConfigProvider, { locale: zhCn }, () => h(App)) })
  .use(createPinia()).use(router).component('ElButton', ElButton).component('ElPagination', ElPagination).mount('#app')

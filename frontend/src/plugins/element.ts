import type { App } from 'vue'
import {
    ElCard,
    ElForm,
    ElFormItem,
    ElInput,
    ElButton,
    ElAlert,
    ElContainer,
    ElAside,
    ElMenu,
    ElMenuItem,
    ElMain,
    ElCollapse,
    ElCollapseItem,
    ElTable,
    ElTableColumn,
    ElTag,
    ElPagination,
    ElDialog,
    ElSelect,
    ElOption,
    ElSwitch,
    ElRow,
    ElCol,
} from 'element-plus'

const components = [
    ElCard,
    ElForm,
    ElFormItem,
    ElInput,
    ElButton,
    ElAlert,
    ElContainer,
    ElAside,
    ElMenu,
    ElMenuItem,
    ElMain,
    ElCollapse,
    ElCollapseItem,
    ElTable,
    ElTableColumn,
    ElTag,
    ElPagination,
    ElDialog,
    ElSelect,
    ElOption,
    ElSwitch,
    ElRow,
    ElCol,
]

export function setupElementPlus(app: App) {
    components.forEach((component) => {
        app.component(component.name!, component)
    })
}

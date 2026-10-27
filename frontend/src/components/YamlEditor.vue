<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { EditorView, keymap } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { yaml } from '@codemirror/lang-yaml'
import { oneDark } from '@codemirror/theme-one-dark'

const props = defineProps({
  modelValue: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const editorContainer = ref(null)
let editorView = null
let isExternalUpdate = false

onMounted(() => {
  const updateListener = EditorView.updateListener.of((update) => {
    if (update.docChanged && !isExternalUpdate) {
      emit('update:modelValue', update.state.doc.toString())
    }
  })

  editorView = new EditorView({
    doc: props.modelValue || '',
    extensions: [
      yaml(),
      oneDark,
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      updateListener,
      EditorView.lineWrapping,
    ],
    parent: editorContainer.value,
  })
})

watch(() => props.modelValue, (newVal) => {
  if (editorView && newVal !== editorView.state.doc.toString()) {
    isExternalUpdate = true
    editorView.dispatch({
      changes: { from: 0, to: editorView.state.doc.length, insert: newVal || '' },
    })
    isExternalUpdate = false
  }
})

onBeforeUnmount(() => {
  editorView?.destroy()
})
</script>

<template>
  <div ref="editorContainer" class="yaml-editor"></div>
</template>

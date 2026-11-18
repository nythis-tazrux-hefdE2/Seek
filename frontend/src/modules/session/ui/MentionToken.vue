<template>
  <span class="mention-ref-token" :class="`mention-ref-${type}`">
    <span class="mention-ref-icon" aria-hidden="true">
      <FileTypeIcon
        v-if="type === 'file'"
        :name="value"
        :is-dir="value.endsWith('/')"
        :size="16"
      />
    </span>
    <span class="mention-ref-label">{{ label }}</span>
  </span>
</template>

<script setup>
import FileTypeIcon from '@/shared/ui/FileTypeIcon.vue'


defineProps({
  type: { type: String, required: true },
  value: { type: String, required: true },
  label: { type: String, required: true }
})
</script>

<style lang="less" scoped>
.mention-ref-token {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  max-width: min(100%, 360px);
  color: var(--main-700);
  line-height: normal;
  vertical-align: baseline;
  white-space: nowrap;
}

.mention-ref-editable {
  user-select: all;
}

.mention-ref-icon {
  position: relative;
  top: 2px;
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  font-size: 13px;
  line-height: 1;
  margin-left: 4px;

  :deep(svg) {
    display: block;
  }
}

.mention-ref-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: normal;
  font-weight: 500;
}
</style>

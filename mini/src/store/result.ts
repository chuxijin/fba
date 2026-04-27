import { reactive } from 'vue'

interface ResultStoreState {
  sessionId: number
  reportData: any
  solutionData: any
  submitResult: any
}

const state = reactive<ResultStoreState>({
  sessionId: 0,
  reportData: null,
  solutionData: null,
  submitResult: null,
})

export function useResultStore() {
  function setResult(sessionId: number, reportData?: any, solutionData?: any, submitResult?: any) {
    state.sessionId = sessionId
    state.reportData = reportData ?? null
    state.solutionData = solutionData ?? null
    state.submitResult = submitResult ?? null
  }

  function clear() {
    state.sessionId = 0
    state.reportData = null
    state.solutionData = null
    state.submitResult = null
  }

  return {
    state,
    setResult,
    clear,
  }
}

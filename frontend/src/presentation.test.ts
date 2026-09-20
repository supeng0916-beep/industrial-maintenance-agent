import { expect, it } from 'vitest'
import { noticeKind } from './presentation'

it('接口不可用优先于上次的新鲜值或成功记录', () => {
  expect(noticeKind({ has_data: true, is_stale: false, last_attempt_status: 'success' }, true, false)).toBe('unverified')
  expect(noticeKind({ has_data: true, is_stale: false, last_attempt_status: 'success' }, false, true)).toBe('unverified')
})

it('无数据、最近失败、旧值与正常数据有不同的操作提示', () => {
  expect(noticeKind(undefined, false, false)).toBe('loading')
  expect(noticeKind({ has_data: false, is_stale: null, last_attempt_status: 'unknown' }, false, false)).toBe('empty')
  expect(noticeKind({ has_data: true, is_stale: false, last_attempt_status: 'failure' }, false, false)).toBe('failure')
  expect(noticeKind({ has_data: true, is_stale: true, last_attempt_status: 'success' }, false, false)).toBe('stale')
  expect(noticeKind({ has_data: true, is_stale: false, last_attempt_status: 'success' }, false, false)).toBe('fresh')
})

it('读到未定义枚举时区分数据校验失败与通信失败', () => {
  expect(noticeKind({has_data:true,is_stale:false,last_attempt_status:'failure',last_failure_type:'data_validation_error'},false,false)).toBe('validation')
})

import assert from 'node:assert/strict'
import test from 'node:test'
import { importTypeScript } from './helpers/typescript.mjs'

const { buildWrongImportItems } = await importTypeScript(new URL('../src/adapters/importer.ts', import.meta.url))
const { formatUserAnswerChoice, pickUserAnswer } = await importTypeScript(
  new URL('../src/adapters/fenbi/normalize.ts', import.meta.url),
)

function imported(userAnswer) {
  return buildWrongImportItems({
    title: '作答回归', source_platform: 'fenbi',
    sections: [{
      name: '言语理解',
      questions: [{ id: 83710, is_wrong: true, stem: '题干', answer: 'C', user_answer: userAnswer }],
    }],
  }).items[0]
}

test('wrong import carries the user single-choice answer', () => {
  assert.equal(imported('B').wrong_response, 'B')
})

test('wrong import splits multiple-choice user answers', () => {
  assert.deepEqual(imported('A,C').wrong_response, ['A', 'C'])
})

test('wrong import omits the snapshot when no user answer was captured', () => {
  assert.equal('wrong_response' in imported(undefined), false)
})

test('fenbi answer sheet numeric choices reach the wrong import payload', () => {
  const answerMap = new Map([['g9001', '1,3']])
  const direct = pickUserAnswer(undefined, answerMap, ['g9001', 9001])
  const paper = {
    title: '粉笔模考', source_platform: 'fenbi',
    sections: [{
      name: '言语理解',
      questions: [{
        id: 9001,
        is_wrong: true,
        stem: '题干',
        answer: 'C',
        user_answer: formatUserAnswerChoice(direct),
      }],
    }],
  }

  assert.equal(formatUserAnswerChoice(direct), 'B,D')
  assert.deepEqual(buildWrongImportItems(paper).items[0].wrong_response, ['B', 'D'])
})

test('a question-owned answer wins over the answer sheet map', () => {
  assert.equal(formatUserAnswerChoice(pickUserAnswer('A', new Map([['g1', '2']]), ['g1'])), 'A')
})

test('wrong import strips visual bold and strong tags from stem and options', () => {
  const paper = {
    title: '错题测试', source_platform: 'fenbi',
    sections: [{
      name: '常识判断',
      questions: [{
        id: 9002,
        is_wrong: true,
        stem: '<p>下列说法<b>不正确</b>的是（ ）。</p>',
        options: ['选项内容 <strong>A</strong>', '选项内容 B'],
        answer: 'A',
      }],
    }],
  }
  const item = buildWrongImportItems(paper).items[0]
  assert.equal(item.stem, '<p>下列说法不正确的是（ ）。</p>')
  assert.equal(item.options[0].content, '选项内容 A')
  assert.equal(item.options[1].content, '选项内容 B')
})


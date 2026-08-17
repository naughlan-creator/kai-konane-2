/*
 * Shared behaviour for the activity and story authoring forms.
 *
 * Both editors are lists of repeated blocks whose field names carry their
 * index (question_1, answer_1_2, page_content_3, ...). Rows can be added,
 * removed and reordered, so every change renumbers the whole list from the top
 * -- that is what keeps the posted field names contiguous, which is what the
 * server walks when it reads the form back.
 */
(function () {
  'use strict';

  function renumberActivity(root) {
    const questions = root.querySelectorAll('[data-question]');
    questions.forEach(function (question, questionIndex) {
      const q = questionIndex + 1;

      question.querySelector('[data-question-label]').textContent = 'Question ' + q;
      setName(question.querySelector('[data-question-id]'), 'question_id_' + q);
      setField(question.querySelector('[data-question-text]'), 'question_' + q);

      question.querySelectorAll('[data-answer]').forEach(function (answer, answerIndex) {
        const a = answerIndex + 1;
        setName(answer.querySelector('[data-answer-id]'), 'answer_id_' + q + '_' + a);
        setField(answer.querySelector('[data-answer-text]'), 'answer_' + q + '_' + a);

        // One radio group per question: a question has exactly one correct
        // answer, which a group of checkboxes could not express.
        const radio = answer.querySelector('[data-answer-correct]');
        radio.name = 'correct_' + q;
        radio.value = String(a);
      });

      // Keep at least two answers; hide the remove button when at the limit.
      const answers = question.querySelectorAll('[data-answer]');
      answers.forEach(function (answer) {
        const remove = answer.querySelector('[data-remove-answer]');
        if (remove) { remove.disabled = answers.length <= 2; }
      });
    });

    questions.forEach(function (question) {
      const remove = question.querySelector('[data-remove-question]');
      if (remove) { remove.disabled = questions.length <= 1; }
      const up = question.querySelector('[data-move-up]');
      const down = question.querySelector('[data-move-down]');
      if (up) { up.disabled = question === questions[0]; }
      if (down) { down.disabled = question === questions[questions.length - 1]; }
    });
  }

  function renumberStory(root) {
    const pages = root.querySelectorAll('[data-page]');
    pages.forEach(function (page, index) {
      const n = index + 1;
      page.querySelector('[data-page-label]').textContent = 'Page ' + n;
      setName(page.querySelector('[data-page-id]'), 'page_id_' + n);
      setField(page.querySelector('[data-page-text]'), 'page_content_' + n);
      setField(page.querySelector('[data-page-upload]'), 'page_image_' + n);
      setField(page.querySelector('[data-page-existing]'), 'page_existing_' + n);

      const remove = page.querySelector('[data-remove-page]');
      if (remove) { remove.disabled = pages.length <= 1; }
      const up = page.querySelector('[data-move-up]');
      const down = page.querySelector('[data-move-down]');
      if (up) { up.disabled = index === 0; }
      if (down) { down.disabled = index === pages.length - 1; }
    });
  }

  function setName(element, name) {
    if (element) { element.name = name; }
  }

  function setField(element, name) {
    if (!element) { return; }
    element.name = name;
    element.id = name;
  }

  function cloneTemplate(id) {
    const template = document.getElementById(id);
    return template.content.firstElementChild.cloneNode(true);
  }

  function moveRow(row, direction, selector) {
    const sibling = direction < 0 ? row.previousElementSibling : row.nextElementSibling;
    if (!sibling || !sibling.matches(selector)) { return; }
    if (direction < 0) {
      row.parentNode.insertBefore(row, sibling);
    } else {
      row.parentNode.insertBefore(sibling, row);
    }
  }

  window.initActivityEditor = function () {
    const list = document.getElementById('questions');
    if (!list) { return; }

    document.getElementById('add-question').addEventListener('click', function () {
      list.appendChild(cloneTemplate('question-template'));
      renumberActivity(list);
    });

    list.addEventListener('click', function (event) {
      const target = event.target;
      const question = target.closest('[data-question]');
      if (!question) { return; }

      if (target.matches('[data-remove-question]')) {
        question.remove();
      } else if (target.matches('[data-add-answer]')) {
        question.querySelector('[data-answers]').appendChild(cloneTemplate('answer-template'));
      } else if (target.matches('[data-remove-answer]')) {
        target.closest('[data-answer]').remove();
      } else if (target.matches('[data-move-up]')) {
        moveRow(question, -1, '[data-question]');
      } else if (target.matches('[data-move-down]')) {
        moveRow(question, 1, '[data-question]');
      } else {
        return;
      }
      renumberActivity(list);
    });

    renumberActivity(list);
  };

  window.initStoryEditor = function () {
    const list = document.getElementById('pages');
    if (!list) { return; }

    document.getElementById('add-page').addEventListener('click', function () {
      list.appendChild(cloneTemplate('page-template'));
      renumberStory(list);
    });

    list.addEventListener('click', function (event) {
      const target = event.target;
      const page = target.closest('[data-page]');
      if (!page) { return; }

      if (target.matches('[data-remove-page]')) {
        page.remove();
      } else if (target.matches('[data-move-up]')) {
        moveRow(page, -1, '[data-page]');
      } else if (target.matches('[data-move-down]')) {
        moveRow(page, 1, '[data-page]');
      } else {
        return;
      }
      renumberStory(list);
    });

    renumberStory(list);
  };

  /* Preview the picture chosen from the library dropdown next to it. */
  window.initImagePickers = function () {
    document.addEventListener('change', function (event) {
      if (!event.target.matches('[data-image-picker]')) { return; }
      const wrapper = event.target.closest('[data-image-field]');
      const preview = wrapper && wrapper.querySelector('[data-image-preview]');
      if (!preview) { return; }
      const filename = event.target.value;
      if (filename) {
        preview.src = preview.dataset.base + filename;
        preview.hidden = false;
      } else {
        preview.hidden = true;
      }
    });
  };
})();

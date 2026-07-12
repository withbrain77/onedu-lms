(function () {
  function fallbackCopy(text) {
    var input = document.createElement('textarea');
    input.value = text;
    input.setAttribute('readonly', '');
    input.style.position = 'fixed';
    input.style.left = '-9999px';
    document.body.appendChild(input);
    input.select();
    try {
      document.execCommand('copy');
      return Promise.resolve();
    } catch (error) {
      return Promise.reject(error);
    } finally {
      document.body.removeChild(input);
    }
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return fallbackCopy(text);
  }

  function setStatus(button, message) {
    var box = button.closest('.course-share-box');
    var status = box ? box.querySelector('[data-course-share-status]') : null;
    if (status) {
      status.textContent = message;
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-course-share-button]').forEach(function (button) {
      var originalText = button.textContent;
      var shareUrl = button.getAttribute('data-course-share-url') || window.location.href;
      var shareTitle = button.getAttribute('data-course-share-title') || document.title;

      button.addEventListener('click', function () {
        if (navigator.share) {
          navigator.share({
            title: shareTitle,
            text: shareTitle + ' 수강 신청 링크',
            url: shareUrl
          }).then(function () {
            setStatus(button, '공유창을 열었습니다.');
          }).catch(function () {
            return copyText(shareUrl).then(function () {
              button.textContent = '복사 완료';
              setStatus(button, '짧은 강의 주소가 복사되었습니다.');
              window.setTimeout(function () {
                button.textContent = originalText;
              }, 1800);
            });
          });
          return;
        }

        copyText(shareUrl).then(function () {
          button.textContent = '복사 완료';
          setStatus(button, '짧은 강의 주소가 복사되었습니다.');
          window.setTimeout(function () {
            button.textContent = originalText;
          }, 1800);
        }).catch(function () {
          setStatus(button, '복사하지 못했습니다. 주소창의 링크를 직접 복사해 주세요.');
        });
      });
    });
  });
})();

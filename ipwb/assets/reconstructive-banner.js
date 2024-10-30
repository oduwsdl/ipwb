/**
 * [ReconstructiveBanner](https://oduwsdl.github.io/Reconstructive/reconstructive-banner.js) implements `<reconstructive-banner>` [Custom Element](https://html.spec.whatwg.org/multipage/custom-elements.html#custom-elements).
 * It is an unobtrusive archival replay banner to make [mementos](http://mementoweb.org/about/) interactive and surface on-demand metadata about the archived resource.
 * The banner houses a customizable branding logo that links to the replay home.
 * It provides a pre-populated text input to navigate the replay to a different URI-R.
 * A brief phrase describes the rough age of the current memento, but can be toggled with the absolute date and time of capture by repeatedly clicking on it.
 * User's preference on absolute or relative datetime display persists across the session.
 * Navigational links to the first, last, previous, and next mementos are also provided when present.
 * In its default floating action bar (FAB) mode it auto-hides after a set duration of inactivity if the banner is not in focus and reappears on any user activity on the page such as scroll, mousemove, or keypress.
 * The FAB can be dragged to repostion it on the page, which then persists across the session unless relocated again.
 * It provides controls to expand, collapse, or completely close the banner.
 * The expanded mode has much more real estate available to house detailed archival metadata and visualizations.
 * Use it in an HTML page as illustrated below:
 *
 * ```html
 * <script src="reconstructive-banner.js"></script>
 * <reconstructive-banner logo-src=""
 *                        home-href="/"
 *                        urir="https://example.com/"
 *                        memento-datetime="Mon, 06 Feb 2017 00:23:37 GMT"
 *                        first-urim="https://archive.host/memento/20170206002337/https://example.com/"
 *                        first-datetime="Mon, 06 Feb 2017 00:23:37 GMT"
 *                        last-urim="https://archive.host/memento/20170206002337/https://example.com/"
 *                        last-datetime="Mon, 06 Feb 2017 00:23:37 GMT"
 *                        prev-urim=""
 *                        prev-datetime=""
 *                        next-urim=""
 *                        next-datetime="">
 * </reconstructive-banner>
 * ```
 *
 * @overview  ReconstructiveBanner implements <reconstructive-banner> Custom Element for archival replay banners.
 * @author    Sawood Alam <ibnesayeed@gmail.com>
 * @license   MIT
 * @copyright ODU Web Science / Digital Libraries Research Group 2017
 */
class ReconstructiveBanner extends HTMLElement {
  constructor() {
    super();

    this.shadow = this.attachShadow({ mode: 'closed' });
  }

  connectedCallback() {
    this.LOGO = 'data:image/svg+xml;charset=utf-8;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxNiAxNiI+PHBhdGggZD0iTTAgMyBhMyAzIDAgMCAxIDMtMyBoMiBsMyAzIGgtMyBhMiAyIDAgMCAwLTIgMiB2NiBhMiAyIDAgMCAwIDIgMiBoMSBsMyAzIGgtNiBhMyAzIDAgMCAxLTMtMyBaIiBmaWxsPSIjMUI0ODY5IiAvPjxwYXRoIGQ9Ik0xNiAxNiBoLTQgbC05LTkgaDYgYTIgMiAwIDAgMCAwLTQgaC0xIGwtMy0zIGg2IGEzIDMgMCAwIDEgMyAzIHY0IGEzIDMgMCAwIDEtMyAzIGgtMSBaIiBmaWxsPSIjRjI0NzM4IiAvPjwvc3ZnPg==';

    this.logoSrc = this.getAttribute('logo-src') || this.LOGO;

    this.homeHref = this.getAttribute('home-href') || '/';

    this.urir = this.getAttribute('urir') || '';

    this.mementoDatetime = this.getAttribute('memento-datetime') || '';

    this.firstUrim = this.getAttribute('first-urim') || '';

    this.firstDatetime = this.getAttribute('first-datetime') || '';

    this.lastUrim = this.getAttribute('last-urim') || '';

    this.lastDatetime = this.getAttribute('last-datetime') || '';

    this.prevUrim = this.getAttribute('prev-urim') || '';

    this.prevDatetime = this.getAttribute('prev-datetime') || '';

    this.nextUrim = this.getAttribute('next-urim') || '';

    this.nextDatetime = this.getAttribute('next-datetime') || '';

    this.timemapUrit = this.getAttribute('timemap-urit') || '';

    this.autoHideDelay = 2000;

    this.displayDatetime = (() => {
      let datetime = { relative: this.mementoDatetime, absolute: this.mementoDatetime };
      const mementoDatetimeObj = new Date(this.mementoDatetime);
      const diff = Date.now() - mementoDatetimeObj;
      if (isNaN(diff)) {
        return datetime;
      }
      let [mementoDate, mementoTime] = mementoDatetimeObj.toISOString().split(/[T\.]/);
      datetime.absolute = `Captured on ${mementoDate} at ${mementoTime} UTC`;
      if (diff < 0) {
        datetime.relative = 'Capture from the future!';
        return datetime;
      }
      const datetimeUnits = ['year', 'month', 'day', 'hour', 'minute', 'second', 'millisecond'];
      let datetimeParts = new Date(diff).toISOString().split(/\D/).map(x => parseInt(x));
      datetimeParts[0] -= 1970;
      datetimeParts[1] -= 1;
      datetimeParts[2] -= 1;
      let primaryUnit, secondaryUnit, primaryQuotient, secondaryQuotient;
      for (let i = 0; i < datetimeUnits.length - 1; i++) {
        if (datetimeParts[i] == 0) {
          continue;
        }
        [primaryUnit, secondaryUnit] = datetimeUnits.slice(i, i + 2);
        [primaryQuotient, secondaryQuotient] = datetimeParts.slice(i, i + 2);
        break;
      }
      let diffStr = `${primaryQuotient} ${primaryUnit}${primaryQuotient != 1 ? 's' : ''}`;
      if (secondaryQuotient > 0) {
        diffStr += ` and ${secondaryQuotient} ${secondaryUnit}${secondaryQuotient != 1 ? 's' : ''}`;
      }
      datetime.relative = `Captured ${diffStr} ago`;
      return datetime;
    })();

    const template = `
      <style>
        a[href=''] {
          pointer-events: none;
          opacity: 0.4;
        }
        #wrapper {
          z-index: 99999999;
          padding: 10px;
          box-sizing: border-box;
        }
        #wrapper.fab {
          position: fixed;
          top: calc(100vh - 100px);
          left: 20px;
        }
        #wrapper.expanded {
          position: fixed;
          top: 0;
          left: 0;
          margin: 0;
          width: 100%;
          height: 100%;
          background: rgba(100, 100, 100, 0.6);
        }
        #wrapper.hidden {
          opacity: 0;
          transition: opacity 0.5s ease-in;
        }
        #wrapper.closed {
          display: none;
        }
        #container {
          border: 2px solid #451212;
          background-color: #F2FFE3;
          border-radius: 10px;
          color: #1B4869;
          max-width: 600px;
          margin: auto;
          padding: 5px;
          box-shadow: 0 0 20px;
          display: grid;
          grid-template-columns: 10px fit-content(300px) 20px 20px 1fr 20px 20px 20px;
          grid-template-rows: 20px 20px 1fr;
          grid-gap: 2px 10px;
          box-sizing: border-box;
          min-height: 50px;
        }
        .expanded #container {
          height: calc(100vh - 20px);
          box-shadow: none;
        }
        .fab #collapse, .fab #meta, .expanded #expand {
          display: none;
        }
        form {
          display: contents;
        }
        input {
          padding: 0 5px;
          box-sizing: border-box;
        }
        .branding {
          height: 42px;
          max-width: 300px;
        }
        .icon {
          width: 20px;
        }
        #drag {
          grid-column: 1;
          grid-row: 1 / 3;
          border: #1B4869 3px dotted;
          cursor: move;
        }
        .expanded #drag {
          opacity: 0.4;
          cursor: default;
        }
        #logo {
          grid-column: 2;
          grid-row: 1 / 3;
        }
        #urir {
          grid-column: 3 / 8;
          grid-row: 1;
        }
        #first {
          grid-column: 3;
          grid-row: 2;
        }
        #prev {
          grid-column: 4;
          grid-row: 2;
        }
        #current {
          grid-column: 5;
          grid-row: 2;
          margin: 0 5px;
          font-size: 16px;
          line-height: 22px;
          color: #323B40;
          text-align: center;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          cursor: default;
          user-select: none;
        }
        .relative {
          cursor: help;
        }
        .precision .relative, .absolute {
          display: none;
        }
        .precision .absolute {
          display: initial;
        }
        #next {
          grid-column: 6;
          grid-row: 2;
        }
        #last {
          grid-column: 7;
          grid-row: 2;
        }
        #close {
          grid-column: 8;
          grid-row: 1;
        }
        #expand {
          grid-column: 8;
          grid-row: 2;
        }
        #collapse {
          grid-column: 8;
          grid-row: 2;
        }
        #meta {
          grid-column: 1 / 9;
          grid-row: 3;
          overflow: auto;
          padding: 10px;
          display: grid;
          grid-template-columns: 1fr 1fr 1fr;
          grid-template-rows: auto auto auto 130px 1fr;
        }
      </style>
      <div id="wrapper" class="fab" style="${localStorage.getItem('bannerPosition') || ''}">
        <div id="container">
          <div id="drag"></div>
          <a id="home" title="Go to home" href="${this.homeHref}" rel="noreferrer">
            <img id="logo" class="branding" src="${this.logoSrc}" alt="Reconstructive Banner Logo">
          </a>
          <form id="lookup">
            <input id="urir" class="url" value="${this.urir}">
          <form>
          <a id="first" class="icon" title="${this.firstDatetime}" href="${this.firstUrim}">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M4 28v-24h4v11l10-10v10l10-10v22l-10-10v10l-10-10v11z"></path></svg>
          </a>
          <a id="prev" class="icon" title="${this.prevDatetime}" href="${this.prevUrim}">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M8 28v-24h4v11l10-10v22l-10-10v11z"></path></svg>
          </a>
          <p id="current" class="datetime ${localStorage.getItem('datetimeDisplay') || ''}" title="${this.mementoDatetime}">
            <span class="relative">${this.displayDatetime.relative}</span>
            <span class="absolute">${this.displayDatetime.absolute}</span>
          </p>
          <a id="next" class="icon" title="${this.nextDatetime}" href="${this.nextUrim}">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M24 4v24h-4v-11l-10 10v-22l10 10v-11z"></path></svg>
          </a>
          <a id="last" class="icon" title="${this.lastDatetime}" href="${this.lastUrim}">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M28 4v24h-4v-11l-10 10v-10l-10 10v-22l10 10v-10l10 10v-11z"></path></svg>
          </a>
          <a id="close" class="icon" href="#">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M31.708 25.708c-0-0-0-0-0-0l-9.708-9.708 9.708-9.708c0-0 0-0 0-0 0.105-0.105 0.18-0.227 0.229-0.357 0.133-0.356 0.057-0.771-0.229-1.057l-4.586-4.586c-0.286-0.286-0.702-0.361-1.057-0.229-0.13 0.048-0.252 0.124-0.357 0.228 0 0-0 0-0 0l-9.708 9.708-9.708-9.708c-0-0-0-0-0-0-0.105-0.104-0.227-0.18-0.357-0.228-0.356-0.133-0.771-0.057-1.057 0.229l-4.586 4.586c-0.286 0.286-0.361 0.702-0.229 1.057 0.049 0.13 0.124 0.252 0.229 0.357 0 0 0 0 0 0l9.708 9.708-9.708 9.708c-0 0-0 0-0 0-0.104 0.105-0.18 0.227-0.229 0.357-0.133 0.355-0.057 0.771 0.229 1.057l4.586 4.586c0.286 0.286 0.702 0.361 1.057 0.229 0.13-0.049 0.252-0.124 0.357-0.229 0-0 0-0 0-0l9.708-9.708 9.708 9.708c0 0 0 0 0 0 0.105 0.105 0.227 0.18 0.357 0.229 0.356 0.133 0.771 0.057 1.057-0.229l4.586-4.586c0.286-0.286 0.362-0.702 0.229-1.057-0.049-0.13-0.124-0.252-0.229-0.357z"></path></svg>
          </a>
          <a id="expand" class="icon" href="#">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M32 0h-13l5 5-6 6 3 3 6-6 5 5z"></path><path d="M32 32v-13l-5 5-6-6-3 3 6 6-5 5z"></path><path d="M0 32h13l-5-5 6-6-3-3-6 6-5-5z"></path><path d="M0 0v13l5-5 6 6 3-3-6-6 5-5z"></path></svg>
          </a>
          <a id="collapse" class="icon" href="#">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><path d="M18 14h13l-5-5 6-6-3-3-6 6-5-5z"></path><path d="M18 18v13l5-5 6 6 3-3-6-6 5-5z"></path><path d="M14 18h-13l5 5-6 6 3 3 6-6 5 5z"></path><path d="M14 14v-13l-5 5-6-6-3 3 6 6-5 5z"></path></svg>
          </a>
          <div id="meta">
            <!-- TODO: Add provenance infomration, metadata, and interactive visualizations here... -->
            test data here lorem
            On open, send Ajax request to ${this.timemapUrit}
            <div id="timemapdata"></div>
          </div>
        </div>
      </div>
    `;
    this.shadow.innerHTML = template;

    const container = this.shadow.getElementById('container');
    const wrapper = this.shadow.getElementById('wrapper');

    let bannerFocused = false;
    container.onmouseover = () => bannerFocused = true;
    container.onmouseout = () => bannerFocused = false;
    let focusTimer;
    const resetTimer = () => {
      wrapper.classList.remove('hidden');
      clearTimeout(focusTimer);
      focusTimer = setTimeout(() => !bannerFocused && wrapper.classList.contains('fab') && wrapper.classList.add('hidden'), this.autoHideDelay);
    };
    window.addEventListener('load', resetTimer);
    window.addEventListener('mousemove', resetTimer);
    window.addEventListener('mousedown', resetTimer);
    window.addEventListener('click', resetTimer);
    window.addEventListener('scroll', resetTimer);
    window.addEventListener('keypress', resetTimer);

    this.shadow.getElementById('close').onclick = e => {
      e.preventDefault();
      wrapper.classList.remove('fab', 'expanded');
      wrapper.classList.add('closed');
    };
    this.shadow.getElementById('expand').onclick = e => {
      e.preventDefault();
      wrapper.classList.replace('fab', 'expanded');
      wrapper.style.removeProperty('top');
      wrapper.style.removeProperty('left');
      console.log(`TODO: perform AJAX request to ${this.timemapUrit}`)
      fetch(this.timemapUrit)
      .then(response => response.json()) // even though we can only get link-format or cdxj TMs for now
      .then(data => this.showtmindom(data))
      .catch(()=>{
      // Exception occurred, do something
      })
    };
    this.shadow.getElementById('collapse').onclick = e => {
      e.preventDefault();
      wrapper.classList.replace('expanded', 'fab');
      wrapper.style.cssText = localStorage.getItem('bannerPosition') || '';
    };
    wrapper.onclick = e => {
      if (e.target == wrapper) {
        wrapper.classList.replace('expanded', 'fab');
        wrapper.style.cssText = localStorage.getItem('bannerPosition') || '';
      }
    };

    this.showtmindom = ((tmdata) => {
      document.getElementById('tmdata').innerHTML = tmdata
    })

    const datetimeDisplay = this.shadow.getElementById('current');
    datetimeDisplay.onclick = e => {
      if (datetimeDisplay.classList.toggle('precision')) {
        localStorage.setItem('datetimeDisplay', 'precision');
      } else {
        localStorage.removeItem('datetimeDisplay');
      }
    };

    let draggable = false;
    let offset = { x: 0, y: 0 };
    this.shadow.getElementById('drag').onmousedown = e => {
      if (wrapper.classList.contains('fab')) {
        draggable = true;
        offset = {
          x: wrapper.offsetLeft - e.clientX,
          y: wrapper.offsetTop - e.clientY
        };
      }
    };
    window.addEventListener('mouseup', e => {
      if (draggable && wrapper.classList.contains('fab')) {
        draggable = false;
        localStorage.setItem('bannerPosition', `left: ${wrapper.offsetLeft}px; top: ${wrapper.offsetTop}px;`);
      }
    });
    window.addEventListener('mousemove', e => {
      e.preventDefault();
      if (draggable && wrapper.classList.contains('fab')) {
        wrapper.style.left = Math.max(Math.min(e.clientX + offset.x, window.innerWidth - 45), 10) + 'px';
        wrapper.style.top = Math.max(Math.min(e.clientY + offset.y, window.innerHeight - 85), 10) + 'px';
      }
    });

    this.shadow.getElementById('lookup').onsubmit = e => {
      e.preventDefault();
      const urir = this.shadow.getElementById('urir').value;
      if (urir) {
        window.location = window.location.href.replace(this.urir, urir);
      }
    };
  }
}

customElements.define('reconstructive-banner', ReconstructiveBanner);

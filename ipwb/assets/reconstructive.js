/**
 * [Reconstructive](https://github.com/oduwsdl/Reconstructive) is a [ServiceWorker](https://www.w3.org/TR/service-workers/) module for client-side reconstruction of composite mementos.
 * It reroutes embedded resource requests to their appropriate archival version without any URL rewriting.
 * It also provides functionality to add custom archival banners or rewrite hyperlinks on the client-side.
 * Use it in a ServiceWorker as illustrated below:
 *
 * ```js
 * importScripts('reconstructive.js');
 * const rc = new Reconstructive();
 * self.addEventListener('fetch', rc.reroute);
 * ```
 *
 * @overview  Reconstructive is a module to be used in a ServiceWorker of an archival replay.
 * @author    Sawood Alam <ibnesayeed@gmail.com>
 * @license   MIT
 * @copyright ODU Web Science / Digital Libraries Research Group 2017
 */
class Reconstructive {
  constructor(config) {
    this.NAME = 'Reconstructive';

    this.VERSION = '0.7.1';

    this.id = `${this.NAME}:${this.VERSION}`;

    this.urimPattern = `${self.location.origin}/memento/<datetime>/<urir>`;

    this.bannerElementLocation = `${self.location.origin}/reconstructive-banner.js`;

    this.bannerLogoLocation = '';

    this.bannerLogoHref = '/';

    this.showBanner = false;

    this.debug = false;

    if (config instanceof Object) {
      for (const [k, v] of Object.entries(config)) {
        this[k] = v;
      }
    }

    this._regexps = {
      urimPattern: new RegExp(`^${this.urimPattern.replace('<datetime>', '(\\d{14})').replace('<urir>', '(.*)')}$`),
      absoluteReference: new RegExp(`(<(iframe|a|meta).*?\\s+(src|href|content\\s*=\\s*["']?\\s*\\d+\\s*;\\s*url)\\s*=\\s*["']?)(https?:\/\/[^'"\\s]+)(.*?>)`, 'ig'),
      bodyEnd: new RegExp('<\/(body|html)>', 'i')
    };

    this.exclusions = {
      notGet: event => event.request.method !== 'GET',
      bannerElement: event => this.showBanner && event.request.url.endsWith(this.bannerElementLocation),
      bannerLogo: event => this.showBanner && this.bannerLogoLocation && event.request.url.endsWith(this.bannerLogoLocation),
      localResource: event => !(this._regexps.urimPattern.test(event.request.url) || this._regexps.urimPattern.test(event.request.referrer))
    };

    this.debug && console.log(`${this.NAME}:${this.VERSION} initialized:`, this);

    this.fetchFailure = this.fetchFailure.bind(this);
  }

  shouldExclude(event) {
    return Object.entries(this.exclusions).some(([exclusionName, exclusionFunc]) => {
      if (exclusionFunc(event)) {
        this.debug && console.log('Exclusion found:', exclusionName, event.request.url);
        return true;
      }
      return false;
    });
  }

  createUrim(event) {
    let [datetime, refUrir] = this.extractDatetimeUrir(event.request.referrer);
    let urir = new URL(event.request.url);

    if (urir.origin === self.location.origin) {
      let refOrigin = refUrir.match(/^(https?:\/\/)?[^\/]+/)[0];
      urir = refOrigin + urir.pathname + urir.search;
    } else {
      urir = urir.href;
    }
    return this.urimPattern.replace('<datetime>', datetime).replace('<urir>', urir);
  }

  extractDatetimeUrir(urim) {
    let [, datetime, urir] = urim.match(this._regexps.urimPattern);

    if (isNaN(datetime)) {
      return [urir, datetime];
    }
    return [datetime, urir];
  }

  createRequest(event) {
    let headers = this.cloneHeaders(event.request.headers);
    headers.set('X-ServiceWorker', this.id);
    return new Request(event.request.url, { headers: headers, redirect: 'manual' });
  }

  cloneHeaders(original) {
    let headers = new Headers();
    for (const [k, v] of original.entries()) {
      headers.append(k, v);
    }
    return headers;
  }

  localRedirect(urim) {
    this.debug && console.log('Locally redirecting to:', urim);
    return Promise.resolve(new Response(`<h1>Locally Redirecting</h1><p>${urim}</p>`, {
      status: 302,
      statusText: 'Found',
      headers: new Headers({
        'Location': urim,
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'text/html'
      })
    }));
  }

  fetchSuccess(response, event) {
    this.debug && console.log('Fetched from server:', response);

    if (response.ok) {
      return this.rewrite(response, event);
    }
    return Promise.resolve(response);
  }

  fetchFailure(error) {
    this.debug && console.log(error);
    return new Response('<h1>Service Unavailable</h1>', {
      status: 503,
      statusText: 'Service Unavailable',
      headers: new Headers({
        'Content-Type': 'text/html'
      })
    });
  }

  rewrite(response, event) {
    if (/text\/html/i.test(response.headers.get('Content-Type'))) {
      let headers = this.cloneHeaders(response.headers);
      let init = {
        status: response.status,
        statusText: response.statusText,
        headers: headers
      };
      return response.text().then(body => {
        const [datetime] = this.extractDatetimeUrir(response.url);

        body = body.replace(this._regexps.absoluteReference, `$1${this.urimPattern.replace('<datetime>', datetime).replace('<urir>', '$4')}$5`);

        if (this.showBanner && event.request.mode === 'navigate') {
          const banner = this.createBanner(response, event);

          if (this._regexps.bodyEnd.test(body)) {
            body = body.replace(this._regexps.bodyEnd, banner + '</$1>');
          } else {
            body += banner;
          }
        }
        return new Response(body, init);
      });
    }
    return Promise.resolve(response);
  }

  createBanner(response, event) {
    let mementoDatetime = response.headers.get('Memento-Datetime') || '';
    const [datetime, urir] = this.extractDatetimeUrir(response.url);
    if (!mementoDatetime) {
      mementoDatetime = new Date(`${datetime.slice(0, 4)}-${datetime.slice(4, 6)}-${datetime.slice(6, 8)}T${datetime.slice(8, 10)}:${datetime.slice(10, 12)}:${datetime.slice(12, 14)}Z`).toUTCString();
    }

    let rels = {};
    const links = response.headers.get('Link');
    if (links) {
      links.replace(/[\r\n]+/g, ' ').replace(/^\W+|\W+$/g, '').split(/\W+</).forEach(l => {
        let segs = l.split(/[>\s'"]*;\W*/);
        let href = segs.shift();
        let attributes = {};
        segs.forEach(s => {
          let [k, v] = s.split(/\W*=\W*/);
          attributes[k] = v;
        });
        attributes['rel'].split(/\s+/).forEach(r => {
          rels[r] = { href: href, datetime: attributes['datetime'] };
        });
      });
    }
    return `
      <script src="${this.bannerElementLocation}"></script>
      <reconstructive-banner logo-src="${this.bannerLogoLocation}"
                             home-href="${this.bannerLogoHref}"
                             urir="${urir}"
                             memento-datetime="${mementoDatetime}"
                             first-urim="${rels.first && rels.first.href || ''}"
                             first-datetime="${rels.first && rels.first.datetime || ''}"
                             last-urim="${rels.last && rels.last.href || ''}"
                             last-datetime="${rels.last && rels.last.datetime || ''}"
                             prev-urim="${rels.prev && rels.prev.href || ''}"
                             prev-datetime="${rels.prev && rels.prev.datetime || ''}"
                             next-urim="${rels.next && rels.next.href || ''}"
                             next-datetime="${rels.next && rels.next.datetime || ''}"
                             timemap-urit="${rels.timemap && rels.timemap.href || ''}">
      </reconstructive-banner>
    `;
  }

  reroute(event) {
    this.debug && console.log('Rerouting requested', event);

    if (this.shouldExclude(event)) return;

    if (this._regexps.urimPattern.test(event.request.url)) {
      let request = this.createRequest(event);
      event.respondWith(fetch(request).then(response => this.fetchSuccess(response, event)).catch(this.fetchFailure));
    } else {
      let urim = this.createUrim(event);
      event.respondWith(this.localRedirect(urim));
    }
  }

}

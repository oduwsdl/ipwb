/* global uris */

function handleSubmit () { // eslint-disable-line no-unused-vars
  const val = document.getElementById('url').value
  if (val) {
    document.location += 'memento/*/' + val
  }
}

function shortestFirst (a, b) {
  return a.replace(/\/+$/, '').split('/').length - b.replace(/\/+$/, '').split('/').length
}

function hideURIs () {
  document.getElementById('uris').classList.add('hidden')
  document.getElementById('memCountListLink').classList.remove('activated')
  window.localStorage.setItem('showURIs', 'false')
}

function splitDatetime (datetime) {
  return datetime.replace(/(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})/, '$1-$2-$3 $4:$5:$6')
}

function addURIListToDOM () {
  const ul = document.getElementById('uriList')
  const uriKeys = Object.keys(uris).sort(shortestFirst)

  uriKeys.forEach(urir => {
    uris[urir].forEach(function (memento) {
      const li = document.createElement('li')
      const a = document.createElement('a')
      const dt = document.createElement('span')
      const title = memento.title || urir

      a.href = 'memento/' + memento.datetime + '/' + urir
      a.appendChild(document.createTextNode(title))
      a.title = title

      dt.setAttribute('class', 'datetime')
      dt.appendChild(document.createTextNode(splitDatetime(memento.datetime)))

      li.appendChild(dt)
      li.appendChild(a)

      li.setAttribute('data-mime', memento.mime)
      li.setAttribute('data-status', memento.status)

      const htmlMIMEs = ['text/html', 'application/xhtml+xml']
      const mementoMIME = memento.mime.split(/\s*;/)[0].toLowerCase()
      const isHTML = htmlMIMEs.includes(mementoMIME)

      const isARedirect = memento.status[0] === '3'
      if (isHTML && !isARedirect) {
        li.setAttribute('data-display', 'default')
      }
      ul.appendChild(li)
    })
  })
}

function showURIs () {
  if (document.getElementById('uriList').childNodes.length === 0) {
    addURIListToDOM() // Prevent multiple adds of the URI list to the DOM
  }

  document.getElementById('memCountListLink').className = ['activated']
  document.getElementById('uris').classList.remove('hidden')
  setPlurality()
  setShowAllButtonStatus()

  setUIExpandedState(uris)
  // Maintain visible state of URI display for future retrieval
  window.localStorage.setItem('showURIs', 'true')
}

function setUIExpandedState (urisObj) {
  const urisHash = calculateURIsHash(urisObj)
  setURIsHash(urisHash)
}

function calculateURIsHash (urisObj) {
  return getStringHashCode(JSON.stringify(urisObj))
}

function getURIsHash () {
  return window.localStorage.getItem('urisHash')
}

function setURIsHash (hashIn) {
  return window.localStorage.setItem('urisHash', hashIn)
}

function getStringHashCode (str) {
  let hash = 0
  let i
  let chr
  if (this.length === 0) {
    return hash
  }
  for (i = 0; i < this.length; i++) {
    chr = this.charCodeAt(i)
    hash = ((hash << 5) - hash) + chr
    hash |= 0 // Convert to 32bit integer
  }
  return hash
}

function toggleURIDisplay () {
  if (window.localStorage.getItem('showURIs') === 'true') {
    hideURIs()
  } else {
    showURIs()
  }
}

function addEventListeners () { // eslint-disable-line no-unused-vars
  const target = document.getElementById('memCountListLink')
  target.addEventListener('click', toggleURIDisplay, false)

  const showAllInListingButton = document.getElementById('showEmbeddedURI')
  showAllInListingButton.onclick = function showAllURIs () {
    const uriList = document.getElementById('uriList')
    if (this.innerHTML === this.dataset.defaultvalue) {
      this.innerHTML = this.dataset.activatedvalue
      uriList.classList.add('forceDisplay')
    } else {
      this.innerHTML = this.dataset.defaultvalue
      uriList.classList.remove('forceDisplay')
    }
  }

  getIPFSWebUIAddress()
  updateServiceWorkerVersionUI()

  const reinstallServiceWorkerButton = document.getElementById('reinstallServiceWorker')
  reinstallServiceWorkerButton.onclick = reinstallServiceWorker

  setShowURIsVisibility()
}

function setShowURIsVisibility () {
  const previousHash = getURIsHash() + ''
  const newHash = calculateURIsHash(uris) + ''

  if (window.localStorage.getItem('showURIs') && previousHash === newHash) {
    showURIs()
  } else {
    hideURIs()
  }
}

function setPlurality () {
  const htmlFilesPlurality = document.getElementById('htmlPages').innerHTML

  if (htmlFilesPlurality === '1') {
    document.getElementById('htmlPagesPlurality').classList.add('hidden')
  }
}

function setShowAllButtonStatus () {
  const urimCount = document.getElementById('memCountInt').innerHTML
  const htmlFilesPlurality = document.getElementById('htmlPages').innerHTML
  if (urimCount === htmlFilesPlurality) {
    document.getElementById('showEmbeddedURI').setAttribute('disabled', 'disabled')
  }
}

function assignStatusButtonHandlers () { // eslint-disable-line no-unused-vars
  const button = document.getElementsByTagName('button')[0]
  if (button.innerHTML === 'Start') {
    button.addEventListener('click', startIPFSDaemon)
  } else {
    button.addEventListener('click', stopIPFSDaemon)
  }
}

function startIPFSDaemon () {
  sendCommandToIPFSDaemon('start')
  this.innerHTML = 'Starting...'
  this.setAttribute('disabled', 'disabled')
}

function stopIPFSDaemon () {
  sendCommandToIPFSDaemon('stop')
  this.innerHTML = 'Stopping...'
  this.setAttribute('disabled', 'disabled')
}

function getIPFSWebUIAddress () {
  const setIPFSWebUILink = function (resp) {
    document.getElementById('webui').setAttribute('href', 'http://' + resp)
  }
  const fail = function () { console.log('fail') }
  const err = function () { console.log('err') }
  makeAnAJAXRequest('/ipfsdaemon/webuilink', setIPFSWebUILink, fail, err)
}

function updateIPFSDaemonButtonUI () {
  window.setTimeout(function () {
    document.location.reload(true)
  }, 4000)
}

function sendCommandToIPFSDaemon (cmd) {
  const failFunction = function () { console.log('Comm w/ ipfs daemon failed.') }
  const errFunction = function () { console.log('Error talking to ipfs daemon.') }
  makeAnAJAXRequest('/ipfsdaemon/' + cmd, updateIPFSDaemonButtonUI,
    failFunction, errFunction)
}

function makeAnAJAXRequest (address, successFunction, failFunction, errorFunction) {
  const xmlhttp = new window.XMLHttpRequest()

  xmlhttp.onreadystatechange = function () {
    if (xmlhttp.readyState === window.XMLHttpRequest.DONE) {
      if (xmlhttp.status === 200) {
        successFunction(xmlhttp.responseText)
      } else if (xmlhttp.status === 400) {
        failFunction()
      } else {
        errorFunction()
      }
    }
  }

  xmlhttp.open('GET', address, true)
  xmlhttp.send()
}

function injectIPWBJS () { // eslint-disable-line no-unused-vars
  registerServiceWorker()
}

function getServiceWorkerVersion () {
  return window.fetch(document.location.href)
    .then(function (resp) {
      return Promise.resolve(resp.headers.get('Server').split('/').at(-1))
    })
}

function reinstallServiceWorker () {
  console.log('Deleting old serviceWorker')
  deleteServiceWorker()
  document.getElementById('serviceWorkerVersion').innerHTML = 'Updating...'
  installServiceWorker()
  updateServiceWorkerVersionUI()
}

function deleteServiceWorker () {
  navigator.serviceWorker.getRegistrations().then(function (registrations) {
    for (const registration of registrations) {
      registration.unregister()
    }
  })
}

function updateServiceWorkerVersionUI () {
  getServiceWorkerVersion().then(function (resp) {
    console.log('updating to ...' + resp)
    document.getElementById('serviceWorkerVersion').innerHTML = 'ver. ' + resp
  })
}

function installServiceWorker () {
  let newInstallation = false

  if (navigator.serviceWorker.controller === null) { // Ideally we would use serviceWorker.getRegistration
    newInstallation = true
  }

  navigator.serviceWorker.register('/ipwbassets/serviceWorker.js', { scope: '/' }).then(
    function (registration) {
      console.log('ServiceWorker registration successful with scope: ', registration.scope)
    }).catch(function (err) {
    console.log('ServiceWorker registration failed: ', err)
  }).then(function (rr) {
    const dt = document.location.href.split('/')[3]
    const viewingMemento = dt.length === 14 && parseInt(dt, 10) + '' === dt

    // Reload the page with processing by the newly installed Service Worker
    if (newInstallation && viewingMemento) {
      document.location.reload()
    }
  })
}

function registerServiceWorker () {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', installServiceWorker)
  } else {
    console.log('Browser does not support Service Worker.')
  }
}

function localizeNumber (numberIn) {
  let clientLocale = navigator.language
  if (navigator.languages && navigator.languages.length) {
    clientLocale = navigator.languages[0]
  }
  return new Intl.NumberFormat(clientLocale).format(numberIn)
}

function setDaemonVersion () {
  const daemonVersion = document.querySelector('#daemonVersion')

  window.fetch('/ipfsdaemon/version')
    .then((response) => response.text())
    .then((txt) => (daemonVersion.innerHTML = txt))
}

window.addEventListener('DOMContentLoaded', (event) => {
  const memCount = document.querySelector('#memCountInt')
  if (!memCount) {
    return // JS file called from two contexts
  }
  memCount.innerHTML = localizeNumber(memCount.innerHTML)

  document.querySelector('#daemonStatus').addEventListener('load', () => { setDaemonVersion() })
})

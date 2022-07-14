// Copyright 2014 Google Inc. All rights reserved.
// 
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

var acdc = {}; // global variable namespace

// Constants
acdc.KB = 1024;
acdc.MB = 1024 * acdc.KB;

// string allocation is done by slicing and/or concatenating this string template
var stringTemplate = 'dkjvalsndv;ibsdvjsSDVK;FUF092U3RUBV09Q2UNVN-0d8fvn2lkju'+
'f;lkdspofgmjbv;lksliw9v8hgcqbnbj092hfnpa;kpjtmga;js;lkd-p0i2jslkjkkjdnnfbaiu'+
'f;lkdspofgmjbv;lksliw9v8hgcqbnbj092hfnpa;kpjtmga;js;lkd-p0i2jslkjkkjdnnfbaiu'+
'f;lkdspofgmjbv;lksliw9v8hgcqbnbj092hfnpa;kpjtmga;js;lkd-p0i2jslkjkkjdnnfbaiu'+
'f;lkdspofgmjbv;lksliw9v8hgcqbnbj092hfnpa;kpjtmga;js;lkd-p0i2jslkjkkjdnnfbaiu'+
'f;lkdspofgmjbv;lksliw9v8hgcqbnbj092hfnpa;kpjtmga;js;lkd-p0i2jslkjkkjdnnfbaiu'+
'f;lkdspofgmjbv;lksliw9v8hgcqbnbj092hfnpa;kpjtmga;js;lkd-p0i2jslkjkkjdnnfbaiu'+
'f;lkdspofgmjbv;lksliw9v8hgcqbnbj092hfnpa;kpjtmga;js;lkd-p0i2jslkjkkjdnnfbaiu'+
'f;lkdspofgmjbv;lksliw9v8hgcqbnbj092hfnpa;kpjtmga;js;lkd-p0i2jslkjkkjdnnfbaiu'+
'slkdfjynvmaljemavvna.sk;oias;kdvhbbxxnnxlwhweoiy109867#^9jVJKCvfio-HBH%Shnra';

// pre-defined log levels
acdc.LOG_DEBUG = 1;
acdc.LOG_INFO  = 2;
acdc.LOG_WARN  = 3;
acdc.LOG_FATAL = 4;

// types of lifetime-size-classes
acdc.LSC_LIST = 1;
acdc.LSC_HEAP = 2;

acdc.NODE_TYPE_ARRAY = 1;
acdc.NODE_TYPE_STRING = 2;
acdc.NODE_TYPE_OBJECT = 3;

acdc.TIMER_PERFORMANCE = 1;
acdc.TIMER_PERFMON = 2;
acdc.TIMER_DATE = 3;

// Runtime vars
acdc.out = undefined; // output channel
acdc.logicalTime = 0;
acdc.heapClass = undefined;
acdc.liveMemSize = 0;
acdc.maxLiveMemSize = 0;

// ACDC Parameters
// either from the command line or from GET variables or default

acdc.option = {};
// default settings for ACDC's Parameters
acdc.option.timeQuantum = 1024;// given in KB;
acdc.option.benchmarkDuration = 100;
acdc.option.minLiveness = 1;
acdc.option.maxLiveness = 10;
acdc.option.minSize = 8;
acdc.option.maxSize = 64;
acdc.option.minRootDistance = 1;
acdc.option.maxRootDistance = 20;
acdc.option.minOutDegree = 0;
acdc.option.maxOutDegree = 5;
acdc.option.minCycleSize = 1;
acdc.option.maxCycleSize = 20;
acdc.option.deallocationDelay = 0;
acdc.option.accessMemory = true;
acdc.option.readOnlyAccess = false;
acdc.option.listHeapRatio = -1; // if -1, determined automatically by type
acdc.option.logLevel = acdc.LOG_FATAL;
acdc.option.timer = acdc.TIMER_DATE; // default is the inaccurate Date.now()
acdc.option.cpuClock = 2000000; // clock speed in kHz for cycle -> ms conversion

// statictical data; instances of TimeData
acdc.allocationTimeData;
acdc.accessTimeData;
acdc.perfMonitor;

/*
 * Representation of timing-based statistical data
 * @param {type} maxNumberOfSamples
 * @returns {TimeData}
 * @constructor
 */
function TimeData(maxNumberOfSamples) {
    this.samples_ = new Array(maxNumberOfSamples);
    this.s_ = 0;
    this.c_ = 0;
}
TimeData.prototype.start = function() {
    switch (acdc.option.timer) {
        case acdc.TIMER_DATE:
            this.s_ = Date.now();
            break;
        case acdc.TIMER_PERFORMANCE:
            this.s_ = performance.now();
            break;
        case acdc.TIMER_PERFMON:
            this.s_ = 0;
            acdc.perfMonitor.start();
            break;
        default:
            acdc.out.fatal('Stopwatch not supportet');
    }
};
TimeData.prototype.stop = function() {
    var stop;    
    switch (acdc.option.timer) {
        case acdc.TIMER_DATE:
            stop = Date.now();
            break;
        case acdc.TIMER_PERFORMANCE:
            stop = performance.now();
            break;
        case acdc.TIMER_PERFMON:
            this.s_ = 0;
            acdc.perfMonitor.stop();
            stop = acdc.perfMonitor.cpu_cycles / acdc.option.cpuClock;
            acdc.perfMonitor.reset();
            break;
        default:
            acdc.out.fatal('Stopwatch not supportet');
    }
    this.samples_[this.c_] = stop - this.s_;
    this.c_++;
};
TimeData.prototype.print = function(message) {
    var avg = arithmeticMean(this.samples_);
    var stddev = standardDeviation(this.samples_, avg);
    var relativeDeviation = (stddev / avg) * 100;
    acdc.out.println(message + 
        ' avg ' + avg.toFixed(3) + 
        ' stddev ' + stddev.toFixed(3) + 
        ' relative ' + relativeDeviation.toFixed(3) + '%',
        message);
};
TimeData.prototype.lastSample = function() {
    return this.samples_[this.c_ - 1].toFixed(3);
};

function arithmeticMean(samples) {
    var sum = 0;
    for (var i = 0; i < samples.length; ++i) {
        sum += samples[i];
    }
    return sum / samples.length;
}
function standardDeviation(samples, average) {
    if (typeof average === 'undefined') {
        average = arithmeticMean(samples);
    }
    var sum = 0;
    for (var i = 0; i < samples.length; ++i) {
        var diff = samples[i] - average;
        diff *= diff;
        sum += diff;
    }
    return Math.sqrt((1/(samples.length-1)) * sum);
}


function applyGETVariables() {
    // Thanks, stackoverflow ;)
    window.location.href.replace(/[?&]+([^=&]+)=([^&]*)/gi, 
        function(m,key,value) {
            if (key in acdc.option) {
                acdc.option[key] = Number(value);
            }
        });
}

function applyCLIArguments(args) {
    for (var i = 0; i < args.length; ++i) {
        if (args[i] in acdc.option) {
            acdc.option[args[i]] = Number(args[i+1]);
            acdc.out.info('CLI Option: ' + args[i] + ' = ' + args[i+1]);
        }
    }
}

function applyParameters(args) {
    applyCLIArguments(args);
    
    if (acdc.option.timer === acdc.TIMER_PERFMON) {
        try {
            acdc.perfMonitor = new PerfMeasurement(PerfMeasurement.CPU_CYCLES);
        } catch (ex) {
            acdc.out.fatal(ex);
        }
    }
    if (acdc.option.timer === acdc.TIMER_PERFORMANCE) {
        if (typeof(performance) === 'undefined') {
            acdc.out.fatal('performance is undefined');
        }
    }
    
    if (typeof(acdc.option.readOnlyAccess) !== 'boolean') {
        if (acdc.option.readOnlyAccess === 1) {
            acdc.option.readOnlyAccess = true;
        } else {
            acdc.option.readOnlyAccess = false;
        }
    }

    if (typeof(acdc.option.accessMemory) !== 'boolean') {
        if (acdc.option.accessMemory === 1) {
            acdc.option.accessMemory = true;
        } else {
            acdc.option.accessMemory = false;
        }
    }
    
    if (acdc.option.minLiveness > acdc.option.maxLiveness) {
        acdc.out.fatal('Parameter error: minLiveness > maxLiveness');
    }
    if (acdc.option.minSize > acdc.option.maxSize) {
        acdc.out.fatal('Parameter error: minSize > maxSize');
    }
    if (acdc.option.minRootDistance > acdc.option.maxRootDistance) {
        acdc.out.fatal('Parameter error: minRootDistance > maxRootDistance');
    }
    if (acdc.option.minOutDegree > acdc.option.maxOutDegree) {
        acdc.out.fatal('Parameter error: minOutDegree > maxOutDegree');
    }
    acdc.option.timeQuantum *= acdc.KB; // parameter is given in KB
}

function printOptions() {
    acdc.out.println('ACDC Settings:');
    for (var key in acdc.option) {
        acdc.out.println(key + ': ' + acdc.option[key]);
    }
    acdc.out.println('---------------------');
}


/**
 * 
 * I/O and other environmental stuff
 */

/**
 * Class representing ACDC's output console
 * @returns {Output}
 * @constructor
 */
function Output () {
}
Output.prototype.println = function(message, id) {
    print(message);
};
Output.prototype.debug = function(message) {
    if (acdc.option.logLevel <= acdc.LOG_DEBUG) {
        this.println(message);
    }
};
Output.prototype.info = function(message) {
    if (acdc.option.logLevel <= acdc.LOG_INFO) {
        this.println(message);
    }
};
Output.prototype.warn = function(message) {
    if (acdc.option.logLevel <= acdc.LOG_WARN) {
        this.println(message);
    }
};
Output.prototype.fatal = function(message) {
    if (acdc.option.logLevel <= acdc.LOG_FATAL) {
        this.println(message);
    }
    throw {name:'FatalError', message: 'Unable to recover'};
};

function setupEnvironment() {
    acdc.out = new Output();
}

/**
 * Distributions: implementation of statictical stuff
 */

/**
 * Retrieves a random integer in [min, max]
 * @param {number} min minimum result
 * @param {number} max maximum result
 */
function RandomNumberBetween(min, max) {
    return Math.floor(Math.random() * (max - min + 1) + min);
}

function Log2(number) {
    return Math.log(number) / Math.LN2;
}

function NumberOfObjects(size, liveness, objectType) {
    // see ACDC paper for that equation
    var size_part = Log2(acdc.option.maxSize) - Log2(size) + 1;
    size_part *= size_part;
    var liveness_part = acdc.option.maxLiveness - liveness + 1;
    liveness_part *= liveness_part;
    // limit number of objects through constant
    var numObjects = (size_part * liveness_part) / 10;

    // distribution depends on objectType.
    if (objectType === acdc.NODE_TYPE_STRING) {
        numObjects *= 2;
    } else if (objectType === acdc.NODE_TYPE_ARRAY) {
        numObjects *= 3;
    } else if (objectType === acdc.NODE_TYPE_OBJECT) {
        numObjects *= 2;
    }
    
    return Math.floor(numObjects + 1);
}

function RandomObjectType() {
    if (acdc.option.listHeapRatio >= 0) {
        // only for objects we can compare lists versus heaps
        return acdc.NODE_TYPE_OBJECT;
    } else {
        return RandomNumberBetween(acdc.NODE_TYPE_ARRAY, acdc.NODE_TYPE_OBJECT);
    }
}

/**
 * Models: implementations of the models. Heap structure and stuff
 */

/**
 * A Node represents an object of a given size
 * @param {number} size
 * @param {number} nodeType
 * @returns {Node}
 * @constructor
 */
function Node(size, nodeType) {
    
    // from now on, we are talking words. Take Node fields into account
    this.size_ = Math.floor(size / 4) - 6; 
    this.size_ = Math.max(1, this.size_);
    this.nodeType_ = nodeType;
    this.outEdges = undefined;
    // this.numberOfInEdges_ = 1;
    this.markCounter_ = 0; // for graph traversal
    this.payload_ = undefined;
    

    if (this.nodeType_ === acdc.NODE_TYPE_ARRAY) {
        this.payload_ = new Array(this.size_);
        for (var i = 0; i < this.size_; ++i) {
            this.payload_[i] = i;
        }
    } else if (this.nodeType_ === acdc.NODE_TYPE_STRING) {
        this.size_ *= 4; // 4 chars per word
        if (this.size_ > stringTemplate.length) {
            this.payload_ = stringTemplate;
            while (this.payload_.length < this.size_) {
                // extend string until it is at least this.size_ long
                this.payload_ = this.payload_.concat(stringTemplate);
            }
        } else {
            this.payload_ = stringTemplate.slice(1, this.size_);
        }
    } else if (this.nodeType_ === acdc.NODE_TYPE_OBJECT) {
        var numberOfOutEdges = RandomNumberBetween(acdc.option.minOutDegree, 
                                                   acdc.option.maxOutDegree);
        // an object cannot have more outEdges than its size
        numberOfOutEdges = Math.min(numberOfOutEdges, this.size_);
        // however, an object needs at least one outEdge
        numberOfOutEdges = Math.max(1, numberOfOutEdges);
        
        this.outEdges = new Array(numberOfOutEdges);
        // reduce size by outEdges. they account as payload as well
        // this.size_ = Math.max(0, (this.size_ - numberOfOutEdges));
        if (this.size_ > 0) {
            this.payload_ = new Array(this.size_);
            for (var i = 0; i < this.size_; ++i) {
                this.payload_[i] = i;
            }
        }
    }
}
// Just some global dummy variables to prevent optimizer from eliminating code
acdc.globalDummyAccessCounter = 0;
acdc.globalDummyString;
Node.prototype.access = function(readOnly) {
    if (typeof(this.payload_) === 'undefined') return;
    
    if (typeof(this.payload_) === 'string') {
        acdc.globalDummyString = this.payload_;
        return;
    }
    
    for (var i = 0; i < this.payload_.length; ++i) {
        var tmp = this.payload_[i] + acdc.globalDummyAccessCounter;
        // dummy access to avoid optimizer to remove read from payload
        if (i > tmp) {
            tmp = tmp + 1;
        } else {
            tmp = tmp + 2;
        }
        if (readOnly === false) {
            // strings are immutable
            if (typeof(this.payload_) !== 'string') {
                this.payload_[i] = tmp+i+acdc.globalDummyAccessCounter;
            }
        }
        acdc.globalDummyAccessCounter += Math.max(tmp,999);
        if (acdc.globalDummyAccessCounter > 1000000) {
            acdc.globalDummyAccessCounter *= -1;
        }
    }
};
Node.prototype.traverse = function(readOnly) {
    this.markCounter_++;
    this.access(readOnly);
    if (typeof(this.outEdges_) === 'undefined') return; // no outedges
    for (var i = 0; i < this.outEdges_.length; ++i) {
        if (typeof(this.outEdges_[i]) === 'undefined') {
            // end of a branch
            continue;
        }
        if (this.markCounter_ > this.outEdges_[i].markCounter) {
            this.outEdges_[i].traverse(readOnly);
        }
    }
};
/*
 * ListNode for building list-based lifetime-size-classes
 * @param {type} payload
 * @returns {ListNode}
 * @constructor
 */
function ListNode(payload) {
    this.payload_ = payload;
    this.next = undefined;
}
ListNode.prototype.access = function(readOnly) {
    // traverse instead of access to also touch outEdges
    this.payload_.traverse(readOnly);
};

/*
 * A List representing a list-based lifetime-size-class
 * @returns {List}
 * @constructor
 */
function List() {
    this.first_ = undefined;
}
List.prototype.append = function(node) {
    if (this.first_ === undefined) {
        this.first_ = node;
    } else {
        node.next = this.first_;
        this.first_ = node;
    }
};
List.prototype.traverse = function(readOnly) {
    var node = this.first_;
    while (node !== undefined) {
        node.access(readOnly);
        node = node.next;
    }
};

function buildHeap(numObjects, size) {
    if (numObjects < 1) {
        return undefined;
    }
    var node = new Node(size, acdc.NODE_TYPE_OBJECT);
    for (var i = 0; i < node.outEdges.length; ++i) {
        // ok, so we reduce the subheap size by the root of the subheap and 
        // divide by the number of sub-heaps
        node.outEdges[i] = buildHeap(
            (Math.floor(numObjects - (i+1)) / node.outEdges.length), size);
    }
    return node;
}

function addShortcuts(node, roots, distanceSoFar, level) {
    // IDEA: create shortcuts to objects that will live longer. 
    // Does not affect ACDC expiration policy
    if (typeof(node) === 'undefined') {
        return;
    }
    
    var randRootDistance = RandomNumberBetween(acdc.option.minRootDistance, 
                                               acdc.option.maxRootDistance);    
    distanceSoFar++;
    
    for (var i = 0; i < node.outEdges.length; ++i) {
        if (typeof(node.outEdges[i]) === 'undefined') {
            return;
        }
        if (distanceSoFar > randRootDistance) {
            roots.push(node.outEdges[i]);
            node.outEdges[i].numberOfInEdges++;
            addShortcuts(node.outEdges[i], roots, 1, level+1);
            acdc.out.debug('shortcut added at level ' + level);
        } else {
            addShortcuts(node.outEdges[i], roots, distanceSoFar, level+1);
        }
    }
}

function addCycles(node, root, level) {
    if (typeof(node) === 'undefined') {
        return;
    }
    
    var randCycleSize = RandomNumberBetween(acdc.option.minCycleSize, 
                                            acdc.option.maxCycleSize);
    var numOut = node.outEdges.length;
    for (var i = 0; i < numOut; ++i) {
        if (typeof(node.outEdges[i]) === 'undefined') {
            continue;
        }
        if ((level % randCycleSize) === 0) {
            node.outEdges.push(root);
            addCycles(node.outEdges[i], node, level+1);
        } else {
            addCycles(node.outEdges[i], root, level+1);
        }
    }
}

/*
 * Representation of a lifetime-size-class
 * @param {number} type
 * @param {number} lifeness
 * @param {number} size
 * @param {number} numObjects
 * @param {number} objectType (array, string, regexp...)
 * @returns {LifetimeSizeClass}
 * @constructor
 */
function LifetimeSizeClass(type, liveness, size, numObjects, objectType) {
    this.lifetime = liveness + acdc.option.deallocationDelay;
    this.size_ = size;
    this.type_ = type;
    this.numObjects_ = numObjects;
    this.objectType_ = objectType;
    this.objects_ = undefined;
    this.roots_ = undefined; // shortcut to some objects to reflect rootDistance
    
    if (this.size_ <= 0) {
        acdc.out.fatal('LifetimeSizeClass parameter error: size ' + size);
    }
    
    if (this.type_ === acdc.LSC_LIST) {
        var rootDistance = RandomNumberBetween(acdc.option.minRootDistance, 
                                               acdc.option.maxRootDistance);
        // how many roots do I need?
        var numberOfRoots = Math.floor(
            Math.max(this.numObjects_ / rootDistance, 1));
        this.roots_ = new Array(numberOfRoots);
        
        this.objects_ = new List();
        for (var i = 0; i < this.numObjects_; ++i) {
            var c = new Node(this.size_, this.objectType_);
            var n = new ListNode(c);
            this.objects_.append(n);
            if ((i % rootDistance) === 0) {
                this.roots_[i] = c;
            }
        }
    } else if (this.type_ === acdc.LSC_HEAP) {
        if (this.objectType_ !== acdc.NODE_TYPE_OBJECT) {
            // just an assertion. taken care of at caller
            acdc.out.fatal('Heap type LSC requires acdc.NODE_TYPE_OBJECT');
        }
        // take care of in and out edges here
                
        // builds a random heap structure without cycles
        this.objects_ = buildHeap(this.numObjects_, this.size_);
        this.roots_ = [];
        
        // take care of root distance, still no cycles
        addShortcuts(this.objects_, this.roots_, 0, 0);
        // well... add cycles now
        addCycles(this.objects_, this, 1);
        
    } else {
        // error handling
        acdc.out.fatal('LivetimeSizeClass Type not supported: ' + type);
    }
    acdc.out.debug('created lsc lt: ' + this.lifetime + 
                   ' sz: ' + this.size_ + 
                   ' num: ' + this.numObjects_ + 
                   ' rd: ' + rootDistance);
}
LifetimeSizeClass.prototype.traverse = function(readOnly) {
    if (typeof readOnly === 'undefined') {
        readOnly = true;
    }
    if (this.type_ === acdc.LSC_LIST) {
        if (this.objectType_ === acdc.NODE_TYPE_STRING) {
            // TODO: readOnly for all immutable types
            this.objects_.traverse(true);
        } else {
            this.objects_.traverse(readOnly);
        }
        
    } else if (this.type_ === acdc.LSC_HEAP) {
        this.objects_.traverse(readOnly);
    } else {
        acdc.out.fatal('LSC type not supported');
    }
};
LifetimeSizeClass.prototype.totalSize = function() {
    return this.size_ * this.numObjects_;
};

function LifetimeClass() {
    this.lifetimeSizeClasses = [];
}
LifetimeClass.prototype.insert = function(lifetimeSizeClass) {
    this.lifetimeSizeClasses.push(lifetimeSizeClass);
};
LifetimeClass.prototype.traverse = function(readOnly) {
    for (var i = 0; i < this.lifetimeSizeClasses.length; ++i) {
        this.lifetimeSizeClasses[i].traverse(readOnly);
    }
};
LifetimeClass.prototype.totalSize = function() {
    var sz = 0;
    for (var i = 0; i < this.lifetimeSizeClasses.length; ++i) {
        sz += this.lifetimeSizeClasses[i].totalSize();
    }
    return sz;
};

/*
 * Represents a heap-class
 * @returns {HeapClass}
 * @constructor
 */
function HeapClass() {
    this.size_ = acdc.option.maxLiveness + acdc.option.deallocationDelay;
    this.lifetimeClasses_ = new Array(this.size_);
    for (var i = 0; i < this.size_; ++i) {
        this.lifetimeClasses_[i] = new LifetimeClass();
    }
}
HeapClass.prototype.insert = function(lifetimeSizeClass) {
    var insertIndex = (acdc.logicalTime + lifetimeSizeClass.lifetime) % 
                       this.size_;
    acdc.out.debug('insert at ' + insertIndex + ' at time ' + acdc.logicalTime + 
                   ' ' + this.size_ + ' ' + lifetimeSizeClass.lifetime);
    this.lifetimeClasses_[insertIndex].insert(lifetimeSizeClass);
    acdc.liveMemSize += (lifetimeSizeClass.size * lifetimeSizeClass.numObjects);
};
HeapClass.prototype.expire = function() {
    var removeIndex = acdc.logicalTime % this.size_;
    acdc.out.debug('expire at ' + removeIndex + ' at time ' + acdc.logicalTime +
                   ' num classes ' +
                   this.lifetimeClasses_[removeIndex].lifetimeSizeClasses.length
                   );
    var expiredLifetimeClass = this.lifetimeClasses_[removeIndex];
    for (var i = 0; i < expiredLifetimeClass.lifetimeSizeClasses.length; ++i) {
        var ltc = expiredLifetimeClass.lifetimeSizeClasses[i];
        acdc.liveMemSize -= (ltc.size * ltc.numObjects);
    }
    this.lifetimeClasses_[removeIndex] = new LifetimeClass();
};
HeapClass.prototype.traverse = function(readOnly) {
    for (var i = 0; i < acdc.option.maxLiveness; ++i) {
        var accessIndex = (acdc.logicalTime + i) % this.size_;
        this.lifetimeClasses_[accessIndex].traverse(readOnly);
    }
};
HeapClass.prototype.totalSize = function() {
    var sz = 0;
    for (var i = 0; i < this.lifetimeClasses_.length; ++i) {
        sz += this.lifetimeClasses_[i].totalSize();
    }
    return sz;
};



/**
 * ACDC: allocation, access, deallocation and stuff
 */

/**
 * ACDC's main routine
 * @param {type} args
 * @returns {undefined}
 */
function executeACDC(args) {
    // make sure the site is already loaded
    setupEnvironment();
    applyParameters(args);
    printOptions();
    
    acdc.heapClass = new HeapClass();
    
    acdc.allocationTimeData = new TimeData(acdc.option.benchmarkDuration);
    acdc.accessTimeData = new TimeData(acdc.option.benchmarkDuration);
    totalSizeSamples = new Array(acdc.option.benchmarkDuration);
    // Date.now() is good enough for overall runtime data
    var runTimeStart = Date.now();
    
    while (acdc.logicalTime < acdc.option.benchmarkDuration) {
        acdc.allocationTimeData.start();
        var tq = 0;
        while (tq < acdc.option.timeQuantum) {
            var randSize = RandomNumberBetween(
                acdc.option.minSize, acdc.option.maxSize);
            // acdc.out.debug('random size: ' + randSize);
            var randLiveness = RandomNumberBetween(
                acdc.option.minLiveness, acdc.option.maxLiveness);
            // acdc.out.debug('random liveness: ' + randLiveness);
            
            var randObjectType = RandomObjectType();
            
            
            var numObjects = NumberOfObjects(randSize, randLiveness, 
                                             randObjectType);
            // acdc.out.debug('number of objects: ' + numObjects);
            
            var randLivetimeSizeClassType;
            if (randObjectType === acdc.NODE_TYPE_STRING 
                    || randObjectType === acdc.NODE_TYPE_ARRAY) {
                // strings cannot be handled in heap type LSC
                randLivetimeSizeClassType = acdc.LSC_LIST;
            } else {
                // select LTSC type based on configured ratio
                if (acdc.option.listHeapRatio >= 0) {
                    var r = RandomNumberBetween(0, 99);
                    if (r >= acdc.option.listHeapRatio) {
                        randLivetimeSizeClassType = acdc.LSC_LIST;
                    } else {
                        randLivetimeSizeClassType = acdc.LSC_HEAP;
                    }
                } else {
                    randLivetimeSizeClassType = RandomNumberBetween(
                        acdc.LSC_LIST, acdc.LSC_HEAP);
                }
            }
            
            var l = new LifetimeSizeClass(randLivetimeSizeClassType, 
                                          randLiveness, randSize, numObjects, 
                                          randObjectType);
            acdc.heapClass.insert(l);

            tq += randSize * numObjects;
        }
        acdc.allocationTimeData.stop();
        
	// output live objects
        totalSizeSamples[acdc.logicalTime] = acdc.heapClass.totalSize();
        acdc.out.info('live memory: ' + totalSizeSamples[acdc.logicalTime]);
        
        acdc.out.debug('Time Quantum overshoot: ' + 
            (tq - acdc.option.timeQuantum));
        acdc.out.info('advancing acdc.logicalTime to '+ acdc.logicalTime + 
            ' in ' + acdc.allocationTimeData.lastSample() + ' ms' + 
            ' after approx ' + tq + ' bytes');
        acdc.out.info('ACDC ' + acdc.logicalTime + ' live=' + 
            (acdc.liveMemSize/1024));
        if (acdc.liveMemSize > acdc.maxLiveMemSize) {
            acdc.maxLiveMemSize = acdc.liveMemSize;
        }
        
        acdc.logicalTime++;
        
        acdc.accessTimeData.start();
        if (acdc.option.accessMemory) {
            acdc.heapClass.traverse(acdc.option.readOnlyAccess);
        }
        acdc.accessTimeData.stop();
        
        acdc.heapClass.expire();
        
    }
    
    var runTimeStop = Date.now();
    acdc.out.println('total runtime ' + (runTimeStop - runTimeStart), 'total');
    acdc.allocationTimeData.print('allocation');
    acdc.accessTimeData.print('access');
    // Testing only
    // var szAvg = arithmeticMean(totalSizeSamples);
    // var szDev = standardDeviation(totalSizeSamples, szAvg);
    // acdc.out.println('live objects avg ' + szAvg.toFixed(1) + ' stddev ' + 
    // szDev.toFixed(1) + ' relative ' + 
    // ((szDev/szAvg)*100).toFixed(1) + '%', 'live');
    // acdc.out.println('ACDC ' + acdc.logicalTime + ' Maxlive=' + 
    // (acdc.maxLiveMemSize/1024));

    acdc.out.println('Dummy output: Can be ignored! ' + 
                     acdc.globalDummyAccessCounter + ' ' + 
                     acdc.globalDummyString);
}

executeACDC(arguments);
